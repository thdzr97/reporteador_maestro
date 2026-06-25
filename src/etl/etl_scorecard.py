"""
etl_scorecard.py — ETL de Score Card por referencia.
Extrae SIR_60_REFERENCIAS + SIR_73_STATUS + SIR_67_MTRA_SELEC_ALEATORIA + nombres de la sábana.
Métrica de despacho: dFechaDespacho IS NOT NULL (campo real, no flag booleano del SIR).
"""
import pandas as pd
import logging
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from src.etl.conexion import query_siradmin, get_pg_engine
from sqlalchemy import text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ETL-SCORECARD] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join(os.path.dirname(__file__), "../../logs/etl_scorecard.log"),
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger(__name__)

TABLA_DESTINO = "scorecard_referencias"

# OUTER APPLY garantiza exactamente una fila por referencia desde la sábana.
# JOIN SIR_67 agrega fechas reales de selección aleatoria.
# despachado = dFechaDespacho IS NOT NULL (bObjCalidadCumplidoDespacho siempre es False en SIR).
QUERY_SCORECARD = """
    SELECT
        r.sReferencia                       AS referencia,
        s.[Ejecutivo]                       AS ejecutivo,
        s.[Cliente]                         AS cliente,
        s.[Nombre Aduana Despacho]          AS aduana,
        s.[Tipo Operación]                  AS tipo_operacion,
        r.dFechaApertura                    AS fecha_apertura,
        r.dFechaCierreOper                  AS fecha_cierre_operativo,
        r.dFechaCierreAdmin                 AS fecha_cierre_administrativo,
        r.nIdStatus73                       AS status_id,
        st.sDescripcion                     AS status_desc,
        r.nDiasObjCalidadDespacho           AS dias_calidad_despacho,
        r.nDiasComodinDespacho              AS dias_comodin_despacho,
        r.nDiasObjCalidadCGA                AS dias_calidad_cga,
        r.nDiasComodinCGA                   AS dias_comodin_cga,
        r.nHonorarios                       AS honorarios,
        r.nAnticipo                         AS anticipo,
        r.nSaldo                            AS saldo,
        r.sObservaciones                    AS observaciones,
        CASE WHEN r.dFechaDespacho IS NOT NULL THEN 1 ELSE 0 END AS despachado,
        r.dFechaDespacho                    AS fecha_despacho,
        sel.dFechaPrimSel                   AS fecha_prim_sel,
        sel.dFechaSegSel                    AS fecha_seg_sel
    FROM sir.SIR_60_REFERENCIAS r
    LEFT JOIN sir.SIR_73_STATUS_REFERENCIAS st
        ON r.nIdStatus73 = st.nIdStatus73
    LEFT JOIN sir.SIR_67_MTRA_SELEC_ALEATORIA sel
        ON r.nIdMtraSelAle67 = sel.nIdMtraSelAle67
    OUTER APPLY (
        SELECT TOP 1
            [Ejecutivo],
            [Cliente],
            [Nombre Aduana Despacho],
            [Tipo Operación]
        FROM [SIRADMIN].[Admin].[SIR_VT_Sabana_Pedimento]
        WHERE [Referencia] = r.sReferencia
        ORDER BY [Pedimento] DESC
    ) s
    WHERE r.dFechaApertura >= '{anio_inicio}-01-01'
"""

COLUMNAS_FECHA = [
    "fecha_apertura", "fecha_cierre_operativo", "fecha_cierre_administrativo",
    "fecha_despacho", "fecha_prim_sel", "fecha_seg_sel",
]


def extraer_scorecard() -> pd.DataFrame:
    anio = datetime.now().year
    query = QUERY_SCORECARD.format(anio_inicio=anio)
    logger.info(f"Extrayendo scorecard para año {anio}")
    df = query_siradmin(query, timeout=600)
    logger.info(f"Extraídos {len(df)} registros")
    return df


def transformar_scorecard(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    for col in COLUMNAS_FECHA:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
            df[col] = df[col].dt.date
    for col in ["honorarios", "anticipo", "saldo"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ["dias_calidad_despacho", "dias_comodin_despacho",
                "dias_calidad_cga", "dias_comodin_cga", "status_id"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    df["despachado"] = df["despachado"].fillna(0).astype(bool)
    df = df.drop_duplicates(subset=["referencia"], keep="first")
    logger.info(f"Transformados {len(df)} registros (únicos por referencia)")
    return df


def cargar_scorecard(df: pd.DataFrame) -> int:
    if df.empty:
        logger.warning("DataFrame vacío, nada que cargar")
        return 0
    engine = get_pg_engine()
    with engine.connect() as conn:
        conn.execute(text(f"TRUNCATE TABLE {TABLA_DESTINO}"))
        conn.commit()
    df.to_sql(TABLA_DESTINO, engine, if_exists="append", index=False)
    logger.info(f"Cargados {len(df)} registros en {TABLA_DESTINO}")
    return len(df)


def run_etl_scorecard():
    logger.info("═══ ETL SCORECARD INICIO ═══")
    df = extraer_scorecard()
    if df.empty:
        logger.error("Extracción vacía — abortando")
        return 0
    df = transformar_scorecard(df)
    n = cargar_scorecard(df)
    logger.info(f"═══ ETL SCORECARD FIN — {n} registros ═══")
    return n


if __name__ == "__main__":
    run_etl_scorecard()
