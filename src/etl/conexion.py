"""
conexion.py — Reporteador Maestro
Conexiones a SIRADMIN (SQL Server) y al data mart (PostgreSQL).
Replica exactamente el driver string de reporte-sir que ya funciona en producción.
"""
import pyodbc
import pandas as pd
import psycopg2
from sqlalchemy import create_engine, text
import os
import logging
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../.env"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── SIRADMIN (SQL Server) ──────────────────────────────────────────────────────
SIRADMIN_DRIVER  = os.getenv("SIRADMIN_DRIVER", "ODBC Driver 18 for SQL Server")
SIRADMIN_HOST    = os.getenv("SIRADMIN_HOST")
SIRADMIN_PORT    = os.getenv("SIRADMIN_PORT", "1433")
SIRADMIN_DB      = os.getenv("SIRADMIN_DB")
SIRADMIN_USER    = os.getenv("SIRADMIN_USER")
SIRADMIN_PASSWORD = os.getenv("SIRADMIN_PASSWORD")

CONN_STR_SIRADMIN = (
    f"DRIVER={{{SIRADMIN_DRIVER}}};"
    f"SERVER={SIRADMIN_HOST},{SIRADMIN_PORT};"
    f"DATABASE={SIRADMIN_DB};"
    f"UID={SIRADMIN_USER};"
    f"PWD={SIRADMIN_PASSWORD};"
    "Encrypt=no;"
    "TrustServerCertificate=yes;"
)

# ── PostgreSQL (data mart local) ───────────────────────────────────────────────
PG_HOST     = os.getenv("POSTGRES_HOST", "127.0.0.1")
PG_PORT     = os.getenv("POSTGRES_PORT", "5432")
PG_DB       = os.getenv("POSTGRES_DB")
PG_USER     = os.getenv("POSTGRES_USER")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD")

PG_URL = (
    f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}"
    f"@{PG_HOST}:{PG_PORT}/{PG_DB}"
)


def query_siradmin(query: str, timeout: int = 300) -> pd.DataFrame:
    """Ejecuta una query en SIRADMIN y devuelve un DataFrame."""
    try:
        with pyodbc.connect(CONN_STR_SIRADMIN, timeout=timeout) as conn:
            df = pd.read_sql(query, conn)
            logger.info(f"SIRADMIN → {len(df)} registros")
            return df
    except pyodbc.Error as e:
        logger.error(f"Error SIRADMIN: {e}")
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"Error inesperado SIRADMIN: {e}")
        return pd.DataFrame()


def get_pg_engine():
    """Devuelve un engine de SQLAlchemy para PostgreSQL (data mart)."""
    return create_engine(PG_URL)


def query_pg(query: str) -> pd.DataFrame:
    """Ejecuta una query en PostgreSQL y devuelve un DataFrame."""
    try:
        engine = get_pg_engine()
        with engine.connect() as conn:
            df = pd.read_sql(text(query), conn)
            logger.info(f"PostgreSQL → {len(df)} registros")
            return df
    except Exception as e:
        logger.error(f"Error PostgreSQL: {e}")
        return pd.DataFrame()


def test_conexiones():
    """Verifica que ambas conexiones responden. Llama este script para validar."""
    print("\n── Test SIRADMIN ─────────────────────────────")
    df = query_siradmin("SELECT TOP 1 1 AS ok")
    print("✓ SIRADMIN OK" if not df.empty else "✗ SIRADMIN FALLÓ")

    print("\n── Test PostgreSQL ───────────────────────────")
    df = query_pg("SELECT 1 AS ok")
    print("✓ PostgreSQL OK" if not df.empty else "✗ PostgreSQL FALLÓ")


if __name__ == "__main__":
    test_conexiones()
