"""
explorar_siradmin.py
Genera diccionario de datos de las vistas SIR relevantes en Markdown.
Solo lectura — no modifica nada en SIRADMIN.
"""
import pyodbc, os, sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(dotenv_path='/var/www/html/ocmx/reporteador-maestro/.env')

CONN_STR = (
    f"DRIVER={{ODBC Driver 18 for SQL Server}};"
    f"SERVER={os.getenv('SIRADMIN_HOST')},{os.getenv('SIRADMIN_PORT')};"
    f"DATABASE={os.getenv('SIRADMIN_DB')};"
    f"UID={os.getenv('SIRADMIN_USER')};"
    f"PWD={os.getenv('SIRADMIN_PASSWORD')};"
    "Encrypt=no;TrustServerCertificate=yes;"
)

VISTAS_SIR = [
    "SIR_VT_Sabana_Pedimento",
    "SIR_VT_Sabana_Pedimento_Admin",
    "SIR_VT_Sabana_Pedimento_MIMPO",
    "SIR_VT_CuentaDeGastos",
    "SIR_VT_CuentaDeGastosFactura",
    "SIR_VT_CCIngresosCobrados",
    "SIR_VT_CCIngresosPendientes",
    "SIR_VT_CCAntiguedadSaldoClientes",
    "SIR_VT_CatalogoClientes",
    "SIR_VT_OperacionesEstatus",
    "SIR_VT_MonitorReferencias",
    "SIR_VT_Liquidaciones",
    "SIR_VT_OchentaVeinte",
    "SIR_VT_EjecutivosOperaciones",
    "SIR_VT_Bookings",
]

def explorar_vista(cursor, vista):
    resultado = {
        "nombre": vista,
        "columnas": [],
        "total_registros": 0,
        "rango_fechas": None,
        "error": None
    }

    try:
        cursor.execute(f"""
            SELECT
                c.COLUMN_NAME,
                c.DATA_TYPE,
                c.CHARACTER_MAXIMUM_LENGTH,
                c.IS_NULLABLE,
                c.COLUMN_DEFAULT
            FROM INFORMATION_SCHEMA.COLUMNS c
            WHERE c.TABLE_NAME = '{vista}'
              AND c.TABLE_CATALOG = 'SIRADMIN'
            ORDER BY c.ORDINAL_POSITION
        """)
        cols = cursor.fetchall()
        resultado["columnas"] = [
            {
                "nombre": r.COLUMN_NAME,
                "tipo": r.DATA_TYPE,
                "longitud": r.CHARACTER_MAXIMUM_LENGTH,
                "nulable": r.IS_NULLABLE,
            }
            for r in cols
        ]

        try:
            cursor.execute(
                f"SELECT COUNT(*) as total FROM [SIRADMIN].[Admin].[{vista}]"
            )
            resultado["total_registros"] = cursor.fetchone().total
        except Exception as e:
            resultado["total_registros"] = f"Error: {e}"

        cols_fecha = [
            c["nombre"] for c in resultado["columnas"]
            if "fecha" in c["nombre"].lower() or "date" in c["nombre"].lower()
        ]
        if cols_fecha:
            col_f = cols_fecha[0]
            try:
                cursor.execute(f"""
                    SELECT
                        MIN([{col_f}]) as f_min,
                        MAX([{col_f}]) as f_max
                    FROM [SIRADMIN].[Admin].[{vista}]
                    WHERE [{col_f}] IS NOT NULL
                """)
                r = cursor.fetchone()
                if r:
                    resultado["rango_fechas"] = {
                        "campo": col_f,
                        "desde": str(r.f_min)[:10] if r.f_min else "N/A",
                        "hasta": str(r.f_max)[:10] if r.f_max else "N/A"
                    }
            except:
                pass

        try:
            cursor.execute(
                f"SELECT TOP 3 * FROM [SIRADMIN].[Admin].[{vista}]"
            )
            rows = cursor.fetchall()
            cols_names = [desc[0] for desc in cursor.description]
            resultado["muestra"] = [
                {cols_names[i]: str(v)[:80] for i, v in enumerate(row)}
                for row in rows
            ]
        except Exception as e:
            resultado["muestra"] = []

    except Exception as e:
        resultado["error"] = str(e)

    return resultado

def generar_markdown(resultados):
    lineas = [
        "# Diccionario de Datos — SIRADMIN",
        f"\nGenerado automáticamente el {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "\nEste documento describe las vistas SIR disponibles para el Reporteador Maestro.",
        "**Pendiente de validación por los analistas del SIR.**",
        "\n---\n",
        "## Índice de vistas\n",
    ]

    for r in resultados:
        estado = "✅" if not r["error"] else "❌"
        total = r["total_registros"]
        lineas.append(f"- {estado} [{r['nombre']}](#{r['nombre'].lower()}) — {total} registros")

    lineas.append("\n---\n")

    for r in resultados:
        lineas.append(f"## {r['nombre']}\n")

        if r["error"]:
            lineas.append(f"**Error al explorar:** `{r['error']}`\n")
            continue

        lineas.append(f"**Total de registros:** {r['total_registros']:,}" if isinstance(r["total_registros"], int) else f"**Total de registros:** {r['total_registros']}")

        if r["rango_fechas"]:
            rf = r["rango_fechas"]
            lineas.append(f"\n**Rango de fechas** (campo `{rf['campo']}`): {rf['desde']} → {rf['hasta']}")

        lineas.append(f"\n**Columnas ({len(r['columnas'])}):**\n")
        lineas.append("| # | Campo | Tipo | Longitud | Nulable | Uso sugerido |")
        lineas.append("|---|-------|------|----------|---------|--------------|")

        for i, c in enumerate(r["columnas"], 1):
            long = str(c["longitud"]) if c["longitud"] else "—"
            lineas.append(
                f"| {i} | `{c['nombre']}` | {c['tipo']} | {long} | {c['nulable']} | _(pendiente)_ |"
            )

        if r.get("muestra"):
            lineas.append(f"\n**Muestra de datos (3 registros):**\n")
            cols = list(r["muestra"][0].keys())
            lineas.append("| " + " | ".join(cols[:8]) + " |")
            lineas.append("|" + "---|" * min(8, len(cols)))
            for row in r["muestra"]:
                vals = [str(row.get(c, ""))[:40] for c in cols[:8]]
                lineas.append("| " + " | ".join(vals) + " |")

        lineas.append("\n**Notas de analistas:** _(pendiente de validación)_\n")
        lineas.append("---\n")

    return "\n".join(lineas)

if __name__ == "__main__":
    print(f"Conectando a SIRADMIN...")
    resultados = []

    with pyodbc.connect(CONN_STR, timeout=30) as conn:
        conn.timeout = 30
        cursor = conn.cursor()

        for i, vista in enumerate(VISTAS_SIR, 1):
            print(f"[{i}/{len(VISTAS_SIR)}] Explorando {vista}...", end=" ", flush=True)
            r = explorar_vista(cursor, vista)
            if r["error"]:
                print(f"ERROR: {r['error'][:60]}")
            else:
                print(f"OK — {r['total_registros']:,} registros, {len(r['columnas'])} columnas")
            resultados.append(r)

    md = generar_markdown(resultados)

    ruta = "/var/www/html/ocmx/reporteador-maestro/docs/diccionario_siradmin.md"
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"\nDiccionario guardado en: {ruta}")
    print(f"Total vistas exploradas: {len(resultados)}")
    print(f"Con error: {sum(1 for r in resultados if r['error'])}")
