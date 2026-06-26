"""
etl_scorecard_v1.py — Score Card hijo v1
Fuente principal: [SIRADMIN].[dbo].[vw_sc_operacion_base]
Lógica validada contra PDF Ocampo GA 25/06/2026
"""
import pyodbc
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import text
import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv('/var/www/html/ocmx/reporteador-maestro/.env')
sys.path.insert(0, '/var/www/html/ocmx/reporteador-maestro')
from src.etl.conexion import get_pg_engine

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [SCV1] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

CONN_STR = (
    f"DRIVER={{ODBC Driver 18 for SQL Server}};"
    f"SERVER={os.getenv('SIRADMIN_HOST')},1433;"
    f"DATABASE=SIRADMIN;"
    f"UID={os.getenv('SIRADMIN_USER')};"
    f"PWD={os.getenv('SIRADMIN_PASSWORD')};"
    "Encrypt=no;TrustServerCertificate=yes;"
)


def dias_habiles(f_ini, f_fin):
    """
    Días hábiles L-V. Sin contar día inicio, sí día fin.
    Verificado: AER2600447I1 19-jun→23-jun = 2 (20=vie, 21=sáb, 22=dom, 23=lun)
    """
    if pd.isna(f_ini) or pd.isna(f_fin):
        return 0
    if isinstance(f_ini, pd.Timestamp):
        f_ini = f_ini.date()
    if isinstance(f_fin, pd.Timestamp):
        f_fin = f_fin.date()
    if f_fin <= f_ini:
        return 0
    dias = 0
    cur = f_ini + timedelta(days=1)
    while cur <= f_fin:
        if cur.weekday() < 5:
            dias += 1
        cur += timedelta(days=1)
    return dias


def extraer(dias_atras=180):
    """Extrae vw_sc_operacion_base con dedup por Ref_prf + JOIN ejecutivo/cliente/honorarios."""
    fecha_ini = (datetime.now() - timedelta(days=dias_atras)).strftime('%Y-%m-%d')

    # CTE con ROW_NUMBER para deduplicar refs con pedimentos complementarios (R1, R2)
    # folio y num_fac son lowercase en la vista
    query = f"""
    WITH base AS (
        SELECT *,
            ROW_NUMBER() OVER (
                PARTITION BY Ref_prf
                ORDER BY FechaExtraccion DESC
            ) AS rn
        FROM [SIRADMIN].[dbo].[vw_sc_operacion_base]
        WHERE FechaPago >= '{fecha_ini}'
           OR EtapaOperacion IN ('EN TRAFICO', 'ADMINISTRATIVO')
    ),
    dedup AS (
        SELECT * FROM base WHERE rn = 1
    )
    SELECT
        d.Ref_prf                   AS referencia,
        d.Ref_cga                   AS ref_cga,
        d.EtapaOperacion            AS etapa_operacion,
        d.Sucursal                  AS sucursal,
        d.ClaveSucursal             AS clave_sucursal,
        d.TipoCargaDesc             AS tipo_carga,
        d.FechaApertura             AS fecha_apertura,
        d.FechaPago                 AS fecha_pago,
        d.FechaPrimeraSeleccion     AS fecha_prim_sel,
        d.FechaAdministrativo       AS fecha_administrativo,
        d.f_e_contabilidad          AS f_e_contabilidad,
        d.FechaCierreAdmin          AS fecha_cierre_adm,
        d.ResultadoSeleccion        AS resultado_seleccion,
        d.ResultadoSeleccionDesc    AS resultado_sel_desc,
        d.folio                     AS folio_proforma,
        d.num_fac                   AS num_fac_cga,
        CASE WHEN d.folio IS NOT NULL THEN 1 ELSE 0 END AS tiene_proforma,
        sab.[Cliente]               AS cliente,
        sab.[Ejecutivo]             AS ejecutivo,
        sab.[Tipo Operación Desc]   AS tipo_operacion,
        sab.[Pedimento Numero]      AS pedimento,
        sab.[Patente]               AS patente,
        CASE WHEN sab.[Pedimento Fecha Pago] IS NOT NULL
             THEN 1 ELSE 0 END      AS pedimento_pagado,
        TRY_CAST(sab.[Honorarios] AS FLOAT) AS honorarios
    FROM dedup d
    OUTER APPLY (
        SELECT TOP 1
            [Cliente],
            [Ejecutivo],
            [Tipo Operación Desc],
            [Pedimento Numero],
            [Patente],
            [Pedimento Fecha Pago],
            [Honorarios]
        FROM [SIRADMIN].[Admin].[SIR_VT_Sabana_Pedimento]
        WHERE [Referencia] = d.Ref_prf
        ORDER BY [Pedimento Fecha Pago] DESC
    ) sab
    """

    logger.info(f"Extrayendo vw_sc_operacion_base desde {fecha_ini}...")
    with pyodbc.connect(CONN_STR, timeout=60) as conn:
        df = pd.read_sql(query, conn)
    logger.info(f"Extraídos {len(df):,} registros")
    return df


def transformar(df):
    """
    Días hábiles con aging acumulativo que PARA cuando cierra la etapa.
    TRF: fecha_prim_sel → f_e_contabilidad (o HOY si aún no cierra)
    ADM: f_e_contabilidad → fecha_cierre_adm (o HOY si aún no cierra)
    CGA: fecha_cierre_adm → HOY
    """
    from datetime import date as _date
    hoy = pd.Timestamp(_date.today())

    fecha_cols = [
        'fecha_pago', 'fecha_prim_sel', 'fecha_administrativo',
        'f_e_contabilidad', 'fecha_cierre_adm', 'fecha_apertura',
    ]
    for col in fecha_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')

    df['honorarios'] = pd.to_numeric(df['honorarios'], errors='coerce')

    # DIAS TRF — para cuando llega f_e_contabilidad
    def calc_trf(r):
        if pd.isna(r['fecha_prim_sel']):
            return 0
        f_fin = r['f_e_contabilidad'] if pd.notna(r['f_e_contabilidad']) else hoy
        return dias_habiles(r['fecha_prim_sel'], f_fin)
    df['dias_trf'] = df.apply(calc_trf, axis=1)

    # DIAS ADM — para cuando llega fecha_cierre_adm
    def calc_adm(r):
        if pd.isna(r['f_e_contabilidad']):
            return 0
        f_fin = r['fecha_cierre_adm'] if pd.notna(r['fecha_cierre_adm']) else hoy
        return dias_habiles(r['f_e_contabilidad'], f_fin)
    df['dias_adm'] = df.apply(calc_adm, axis=1)

    # DIAS CGA — aging desde cierre hasta hoy
    def calc_cga(r):
        if pd.isna(r['fecha_cierre_adm']):
            return 0
        return dias_habiles(r['fecha_cierre_adm'], hoy)
    df['dias_cga'] = df.apply(calc_cga, axis=1)

    df['tiene_proforma'] = df['tiene_proforma'].fillna(0).astype(bool)
    df['pedimento_pagado'] = df['pedimento_pagado'].fillna(0).astype(bool)

    # Convertir fechas a Python date para PostgreSQL
    for col in fecha_cols:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: x.date() if pd.notna(x) else None)

    return df


def cargar(df):
    """DELETE + INSERT completo (scorecard_v1 se recarga en cada ciclo ETL)."""
    engine = get_pg_engine()
    cols = [
        'referencia', 'ref_cga', 'cliente', 'pedimento', 'patente',
        'sucursal', 'clave_sucursal', 'ejecutivo', 'tipo_operacion', 'tipo_carga',
        'fecha_apertura', 'fecha_pago', 'fecha_prim_sel', 'fecha_administrativo',
        'f_e_contabilidad', 'fecha_cierre_adm',
        'resultado_seleccion', 'resultado_sel_desc', 'etapa_operacion',
        'dias_trf', 'dias_adm', 'dias_cga',
        'tiene_proforma', 'folio_proforma', 'num_fac_cga',
        'pedimento_pagado', 'honorarios',
    ]
    df_load = df[[c for c in cols if c in df.columns]].copy()
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM scorecard_v1"))
        df_load.to_sql(
            'scorecard_v1', conn,
            if_exists='append', index=False,
            method='multi', chunksize=500,
        )
    logger.info(f"Cargados {len(df_load):,} registros en scorecard_v1")
    return len(df_load)


def run_etl_scorecard_v1():
    logger.info("═══ ETL SCORECARD_V1 INICIO ═══")
    df = extraer(dias_atras=180)
    df = transformar(df)
    etapas = df['etapa_operacion'].value_counts().to_dict()
    n = cargar(df)

    print(f"\n{'='*50}")
    print(f"Score Card v1 — Resumen")
    print(f"{'='*50}")
    print(f"Total:  {n:,}")
    for e, c in sorted(etapas.items()):
        print(f"  {e:<20} {c:,}")
    print(f"Con proforma:   {int(df['tiene_proforma'].sum()):,}")
    print(f"Con factura:    {int(df['num_fac_cga'].notna().sum()):,}")
    print(f"{'='*50}")
    logger.info("═══ ETL SCORECARD_V1 FIN ═══")
    return n


if __name__ == "__main__":
    run_etl_scorecard_v1()
