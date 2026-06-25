"""
etl_cumplimiento.py — Reporteador Maestro
Extrae SIR_VT_Sabana_Pedimento de SIRADMIN y carga en PostgreSQL.
Consulta base replicada de reporte-sir/reportes/dashboard_cumplimiento.py
"""
import pandas as pd
import logging
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from src.etl.conexion import query_siradmin, get_pg_engine
from sqlalchemy import text, inspect, MetaData
from sqlalchemy.dialects.postgresql import insert as pg_insert

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join(os.path.dirname(__file__), "../../logs/etl_cumplimiento.log"),
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger(__name__)

TABLA_DESTINO = "cumplimiento_pedimentos"

QUERY_EXTRACCION = """
    SELECT DISTINCT
        [Referencia],
        [Patente],
        [Nombre Aduana Despacho],
        [Cliente],
        [Clave Pedimento],
        [Tipo Operación],
        [MedioTransporte],
        [Contenedores],
        [TipoContenedor],
        [FechaRevalidacion],
        [Fecha Entrada/Presentación] AS FechaArribo,
        [ Fecha de Pago] AS FechaPago,
        [Pedimento Fecha Pago],
        [Fechas de Cuentas de Gastos],
        [FE Contabilidad],
        [Pedimento]
    FROM [SIRADMIN].[Admin].[SIR_VT_Sabana_Pedimento]
    WHERE [Pedimento Fecha Pago] >= '{fecha_inicio}'
      AND [Pedimento Fecha Pago] <= '{fecha_fin}'
      AND [Pedimentos Pagados] = 1
      AND [Pedimento] IS NOT NULL
      AND [Pedimento] <> '6000000'
      AND [Clave Pedimento] NOT IN ('V1', 'R1', 'V5', 'F4', 'F5', 'RC')
"""

COLUMNAS_RENOMBRADAS = {
    "Referencia": "referencia",
    "Patente": "patente",
    "Nombre Aduana Despacho": "aduana",
    "Cliente": "cliente",
    "Clave Pedimento": "clave_pedimento",
    "Tipo Operación": "tipo_operacion",
    "MedioTransporte": "medio_transporte",
    "Contenedores": "contenedores",
    "TipoContenedor": "tipo_contenedor",
    "FechaRevalidacion": "fecha_revalidacion",
    "FechaArribo": "fecha_arribo",
    "FechaPago": "fecha_pago",
    "Pedimento Fecha Pago": "pedimento_fecha_pago",
    "Fechas de Cuentas de Gastos": "fecha_cuenta_gastos",
    "FE Contabilidad": "fecha_contabilidad",
    "Pedimento": "pedimento",
}

COLUMNAS_FECHA = [
    "fecha_revalidacion",
    "fecha_arribo",
    "fecha_pago",
    "pedimento_fecha_pago",
    "fecha_cuenta_gastos",
    "fecha_contabilidad",
]


def extraer(fecha_inicio: str, fecha_fin: str) -> pd.DataFrame:
    """Extrae datos de SIRADMIN para el rango de fechas dado (formato YYYYMMDD)."""
    query = QUERY_EXTRACCION.format(fecha_inicio=fecha_inicio, fecha_fin=fecha_fin)
    logger.info(f"Extrayendo SIRADMIN: {fecha_inicio} → {fecha_fin}")
    df = query_siradmin(query, timeout=600)
    logger.info(f"Extraídos {len(df)} registros")
    return df


def transformar(df: pd.DataFrame) -> pd.DataFrame:
    """Renombra columnas a snake_case y convierte fechas."""
    if df.empty:
        return df
    df = df.rename(columns=COLUMNAS_RENOMBRADAS)
    for col in COLUMNAS_FECHA:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")
    df = df.drop_duplicates(subset=["referencia", "pedimento"], keep="first")
    # La clave única en BD es pedimento — eliminar duplicados por esa clave
    df = df.drop_duplicates(subset=["pedimento"], keep="first")
    # Convertir fechas a Python date/None para compatibilidad con pg_insert
    for col in COLUMNAS_FECHA:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: x.date() if pd.notna(x) else None)
    logger.info(f"Transformados {len(df)} registros (después de dedup)")
    return df


def cargar(df: pd.DataFrame, modo: str = "replace") -> int:
    """Carga DataFrame en PostgreSQL.
    modo='replace': TRUNCATE+INSERT (preserva constraint UNIQUE).
    modo='upsert':  INSERT ON CONFLICT(pedimento) DO UPDATE.
    """
    if df.empty:
        logger.warning("DataFrame vacío, nada que cargar")
        return 0
    engine = get_pg_engine()

    if modo == "replace":
        tabla_existe = TABLA_DESTINO in inspect(engine).get_table_names()
        if tabla_existe:
            with engine.begin() as conn:
                conn.execute(text(f"TRUNCATE TABLE {TABLA_DESTINO}"))
            df.to_sql(TABLA_DESTINO, engine, if_exists="append", index=False)
        else:
            df.to_sql(TABLA_DESTINO, engine, if_exists="replace", index=False)
            with engine.begin() as conn:
                conn.execute(text(
                    f"ALTER TABLE {TABLA_DESTINO} "
                    f"ADD CONSTRAINT uq_cumpl_pedimento UNIQUE (pedimento)"
                ))
    elif modo == "upsert":
        with engine.connect() as conn:
            meta = MetaData()
            meta.reflect(bind=conn, only=[TABLA_DESTINO])
        tabla = meta.tables[TABLA_DESTINO]
        records = df.to_dict(orient="records")
        with engine.begin() as conn:
            for i in range(0, len(records), 500):
                chunk = records[i:i + 500]
                stmt = pg_insert(tabla).values(chunk)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["pedimento"],
                    set_={col: stmt.excluded[col]
                          for col in df.columns if col != "pedimento"}
                )
                conn.execute(stmt)
    else:
        df.to_sql(TABLA_DESTINO, engine, if_exists="append", index=False)

    logger.info(f"Cargados {len(df):,} registros en {TABLA_DESTINO} (modo={modo})")
    return len(df)


def etl_completo(meses_atras: int = 12):
    """ETL completo: extrae los últimos N meses desde SIRADMIN y reemplaza en PostgreSQL."""
    hoy = datetime.now()
    fecha_inicio = (hoy - timedelta(days=meses_atras * 30)).strftime("%Y%m%d")
    fecha_fin = hoy.strftime("%Y%m%d")

    logger.info(f"═══ ETL CUMPLIMIENTO INICIO ({fecha_inicio} → {fecha_fin}) ═══")

    df = extraer(fecha_inicio, fecha_fin)
    if df.empty:
        logger.error("Extracción vacía — abortando")
        return

    df = transformar(df)
    n = cargar(df, modo="replace")

    logger.info(f"═══ ETL CUMPLIMIENTO FIN — {n} registros cargados ═══")
    return n


def etl_incremental():
    """ETL incremental: extrae últimos 7 días y hace UPSERT por pedimento."""
    hoy = datetime.now()
    fecha_inicio = (hoy - timedelta(days=7)).strftime("%Y%m%d")
    fecha_fin = hoy.strftime("%Y%m%d")

    logger.info(f"── ETL incremental ({fecha_inicio} → {fecha_fin}) ──")

    df = extraer(fecha_inicio, fecha_fin)
    if df.empty:
        logger.info("Sin datos nuevos en los últimos 7 días")
        return 0

    df = transformar(df)
    n = cargar(df, modo="upsert")
    logger.info(f"── ETL incremental FIN — {n} registros actualizados ──")
    return n


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ETL Cumplimiento Pedimentos")
    parser.add_argument(
        "--modo",
        choices=["completo", "incremental"],
        default="completo",
        help="completo=últimos 12 meses (replace), incremental=últimos 7 días (upsert)",
    )
    parser.add_argument(
        "--meses", type=int, default=12, help="Meses hacia atrás (solo modo completo)"
    )
    args = parser.parse_args()

    if args.modo == "completo":
        etl_completo(meses_atras=args.meses)
    else:
        etl_incremental()
