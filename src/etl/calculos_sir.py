"""
calculos_sir.py — Bridge de importación desde reporte-sir.
Importa las funciones de cálculo de cumplimiento sin replicar código.
"""
import sys
sys.path.insert(0, '/var/www/html/ocmx/reporte-sir')
from utils.calculos import (
    dias_habiles_oga,
    obtener_fecha_mas_reciente,
    clasificar_transporte,
    meta_dinamica,
    obtener_mes_espanol
)

METAS_OPERATIVO = {
    'AÉREO': 3,
    'TERRESTRE': 3,
    'MARÍTIMO - CARGA SUELTA': 10,
    'MARÍTIMO - CONTENEDOR': 10,
}

METAS_ADMINISTRATIVO = {
    'AÉREO': 3,
    'TERRESTRE': 7,
    'MARÍTIMO - CARGA SUELTA': 3,
    'MARÍTIMO - CONTENEDOR': 10,
}

METAS_OPERATIVO_EXPO = {
    'AÉREO': 3,
    'TERRESTRE': 3,
    'MARÍTIMO - CARGA SUELTA': 8,
    'MARÍTIMO - CONTENEDOR': 8,
}

if __name__ == "__main__":
    from datetime import datetime
    print("✓ Import exitoso")
    print(f"  dias_habiles_oga: {dias_habiles_oga}")
    print(f"  meta_dinamica: {meta_dinamica}")
    print(f"  clasificar_transporte: {clasificar_transporte}")
    d = dias_habiles_oga(datetime(2026, 6, 1), datetime(2026, 6, 10))
    print(f"  Test dias_habiles_oga(jun 1 → jun 10) = {d} días hábiles")
