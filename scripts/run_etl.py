"""
run_etl.py — Ejecuta el ETL de cumplimiento en bucle continuo.
Corre cada 90 segundos. Arrancar con nohup, detener con pkill.
"""
import time
import logging
import sys
import os

sys.path.insert(0, '/var/www/html/ocmx/reporteador-maestro')
os.chdir('/var/www/html/ocmx/reporteador-maestro')

from dotenv import load_dotenv
load_dotenv()

from src.etl.etl_cumplimiento import etl_incremental
from src.etl.etl_sabana import run_etl_sabana
from src.etl.etl_scorecard import run_etl_scorecard

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [ETL] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('logs/etl.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

INTERVALO = int(os.getenv('ETL_INTERVALO_SEGUNDOS', 90))

logger.info(f"ETL continuo arrancado. Intervalo: {INTERVALO}s")

while True:
    try:
        etl_incremental()
    except Exception as e:
        logger.error(f"Error en ciclo ETL cumplimiento: {e}")

    try:
        run_etl_sabana(dias_atras=2)
    except Exception as e:
        logger.error(f"Error ETL sábana: {e}")

    try:
        run_etl_scorecard()
    except Exception as e:
        logger.error(f"Error ETL scorecard: {e}")

    time.sleep(INTERVALO)
