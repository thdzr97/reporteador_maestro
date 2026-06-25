"""
etl_sabana.py — ETL de Sábana de Pedimentos, una fila por referencia.
GROUP BY [Referencia] en origen para eliminar duplicados de fracciones/pedimentos.
Estrategia: MAX para descriptivos y fechas, SUM para totales financieros y conteos.
"""
import pandas as pd
import logging
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from src.etl.conexion import query_siradmin, get_pg_engine
from sqlalchemy import text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ETL-SABANA] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join(os.path.dirname(__file__), "../../logs/etl_sabana.log"),
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger(__name__)

TABLA_DESTINO = "sabana_pedimentos"

# GROUP BY [Referencia]: una fila por referencia.
# TRY_CAST para columnas numéricas que la vista entrega como varchar.
# STUFF/FOR XML PATH para concatenar fracciones únicas por referencia.
QUERY_SABANA = """
    SELECT
        sp.[Referencia],
        MAX([Referencia Fecha Apertura])                        AS [Referencia Fecha Apertura],
        MAX([Pedimento Fecha Pago])                             AS [Pedimento Fecha Pago],
        MAX([Ejecutivo])                                        AS [Ejecutivo],
        MAX([Cliente])                                          AS [Cliente],
        MAX([Nombre Aduana Despacho])                           AS [Nombre Aduana Despacho],
        MAX([Nombre Aduana Entrada])                            AS [Nombre Aduana Entrada],
        MAX([Tipo Operación])                                   AS [Tipo Operación],
        MAX([Régimen])                                          AS [Régimen],
        MAX([Status/Observaciones])                             AS [Status/Observaciones],
        MAX([Primera Selección])                                AS [Primera Selección],
        MAX([Segunda Selección])                                AS [Segunda Selección],
        MAX(TRY_CAST([Valor Aduana] AS FLOAT))                  AS [Valor Aduana],
        MAX(TRY_CAST([Honorarios] AS FLOAT))                    AS [Honorarios],
        SUM(ISNULL(TRY_CAST([TotalCGA] AS FLOAT), 0))          AS [TotalCGA],
        SUM(ISNULL(TRY_CAST([CantidadFacturas] AS BIGINT), 0)) AS [CantidadFacturas],
        SUM(ISNULL(TRY_CAST([CantidadPartidas] AS BIGINT), 0)) AS [CantidadPartidas],
        MAX([Pedimento])                                        AS [Pedimento],
        MAX([Patente])                                          AS [Patente],
        MAX([Clave Cliente])                                    AS [Clave Cliente],
        MAX([Clave Incoterm])                                   AS [Clave Incoterm],
        MAX([Nombre País Vendedor/Comprador])                   AS [Nombre País Vendedor/Comprador],
        MAX([Nombre País Origen/Destino])                       AS [Nombre País Origen/Destino],
        MAX([CovesFactura])                                     AS [CovesFactura],
        MAX([FechaRevalidacion])                                AS [FechaRevalidacion],
        MAX([Fecha primera Selección])                          AS [Fecha primera Selección],
        MAX([Fecha Segunda Selección])                          AS [Fecha Segunda Selección],
        MAX([Pedimento Fecha de Elaboracion])                   AS [Pedimento Fecha de Elaboracion],
        MAX([Fecha Entrada/Presentación])                       AS [Fecha Entrada/Presentación],
        MAX([ObservacionesR])                                   AS [ObservacionesR],
        STUFF((
            SELECT DISTINCT ', ' + CAST(sub.[Fracciones] AS VARCHAR(20))
            FROM [SIRADMIN].[Admin].[SIR_VT_Sabana_Pedimento] sub
            WHERE sub.[Referencia] = sp.[Referencia]
              AND sub.[Pedimento Fecha Pago] >= '{fecha_inicio}'
              AND sub.[Fracciones] IS NOT NULL
              AND sub.[Fracciones] <> ''
            FOR XML PATH('')
        ), 1, 2, '')                                            AS fracciones_lista
    FROM [SIRADMIN].[Admin].[SIR_VT_Sabana_Pedimento] sp
    WHERE [Pedimento Fecha Pago] >= '{fecha_inicio}'
      AND [Pedimento Fecha Pago] IS NOT NULL
      AND [Pedimentos Pagados] = 1
      AND [Pedimento] IS NOT NULL
      AND [Pedimento] <> '6000000'
      AND [Clave Pedimento] NOT IN ('V1', 'R1', 'V5', 'F4', 'F5', 'RC')
    GROUP BY sp.[Referencia]
"""

COLUMNAS_RENOMBRADAS = {
    "Referencia": "referencia",
    "Pedimento": "pedimento",
    "Pedimento Fecha Pago": "fecha_pago",
    "Referencia Fecha Apertura": "fecha_apertura",
    "Cliente": "cliente",
    "Clave Cliente": "rfc_cliente",
    "Ejecutivo": "ejecutivo",
    "Nombre Aduana Despacho": "aduana_despacho",
    "Nombre Aduana Entrada": "aduana_entrada",
    "Tipo Operación": "tipo_operacion",
    "Régimen": "regimen",
    "Status/Observaciones": "status_referencia",
    "Primera Selección": "primera_seleccion",
    "Segunda Selección": "segunda_seleccion",
    "Valor Aduana": "valor_aduana",
    "Honorarios": "honorarios",
    "TotalCGA": "total_cga",
    "Nombre País Origen/Destino": "pais_origen_destino",
    "Nombre País Vendedor/Comprador": "pais_vendedor_comprador",
    "Clave Incoterm": "incoterm",
    "fracciones_lista": "fracciones",
    "CovesFactura": "coves_factura",
    "CantidadFacturas": "cantidad_facturas",
    "CantidadPartidas": "cantidad_partidas",
    "Patente": "patente",
    "FechaRevalidacion": "fecha_revalidacion",
    "Fecha primera Selección": "fecha_primera_seleccion",
    "Fecha Segunda Selección": "fecha_segunda_seleccion",
    "Pedimento Fecha de Elaboracion": "fecha_elaboracion",
    "Fecha Entrada/Presentación": "fecha_entrada",
    "ObservacionesR": "observaciones",
}

COLUMNAS_FECHA = [
    "fecha_pago", "fecha_apertura", "fecha_revalidacion",
    "fecha_primera_seleccion", "fecha_segunda_seleccion",
    "fecha_elaboracion", "fecha_entrada",
]


def extraer_sabana(dias_atras: int = 30) -> pd.DataFrame:
    fecha_inicio = (datetime.now() - timedelta(days=dias_atras)).strftime("%Y%m%d")
    query = QUERY_SABANA.format(fecha_inicio=fecha_inicio)
    logger.info(f"Extrayendo sábana desde {fecha_inicio} (GROUP BY referencia)")
    df = query_siradmin(query, timeout=600)
    logger.info(f"Extraídos {len(df)} referencias únicas de sábana")
    return df


def transformar_sabana(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.rename(columns=COLUMNAS_RENOMBRADAS)
    for col in COLUMNAS_FECHA:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")
            df[col] = df[col].dt.date
    for col in ["valor_aduana", "honorarios", "total_cga"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ["cantidad_facturas", "cantidad_partidas"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    logger.info(f"Transformadas {len(df)} referencias")
    return df


def cargar_sabana(df: pd.DataFrame) -> int:
    if df.empty:
        logger.warning("DataFrame vacío, nada que cargar")
        return 0
    engine = get_pg_engine()
    with engine.connect() as conn:
        refs = df["referencia"].unique().tolist()
        batch_size = 500
        for i in range(0, len(refs), batch_size):
            batch = refs[i:i + batch_size]
            placeholders = ",".join([f":r{j}" for j in range(len(batch))])
            params = {f"r{j}": v for j, v in enumerate(batch)}
            conn.execute(
                text(f"DELETE FROM {TABLA_DESTINO} WHERE referencia IN ({placeholders})"),
                params,
            )
        conn.commit()
    df.to_sql(TABLA_DESTINO, engine, if_exists="append", index=False)
    logger.info(f"Cargadas {len(df)} referencias en {TABLA_DESTINO}")
    return len(df)


def run_etl_sabana(dias_atras: int = 30):
    logger.info(f"═══ ETL SÁBANA INICIO (últimos {dias_atras} días, 1 fila/referencia) ═══")
    df = extraer_sabana(dias_atras)
    if df.empty:
        logger.error("Extracción vacía — abortando")
        return 0
    df = transformar_sabana(df)
    n = cargar_sabana(df)
    logger.info(f"═══ ETL SÁBANA FIN — {n} referencias ═══")
    return n


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ETL Sábana de Pedimentos (1 fila por referencia)")
    parser.add_argument("--dias", type=int, default=180, help="Días hacia atrás")
    args = parser.parse_args()
    run_etl_sabana(dias_atras=args.dias)
