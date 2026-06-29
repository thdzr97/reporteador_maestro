"""cumplimiento.py — Dashboard de Cumplimiento (Reporteador Maestro)
Replica render_dashboard() de reporte-sir pero leyendo PostgreSQL en vez de SIRADMIN.
"""
import sys
import os
import io
import tempfile
import hashlib
import logging
from datetime import date, datetime
from io import BytesIO

_logger = logging.getLogger(__name__)

import pandas as pd
import plotly.express as px
import streamlit as st

# ── funciones compartidas de reporte-sir ─────────────────────────────────────
sys.path.insert(0, "/var/www/html/ocmx/reporte-sir")
from utils.calculos import (
    dias_habiles_oga,
    obtener_fecha_mas_reciente,
    clasificar_transporte,
    meta_dinamica,
    obtener_mes_espanol,
)

# ── conexión PostgreSQL ───────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from src.etl.conexion import get_pg_engine, query_pg
from sqlalchemy import text as sql_text


# ══════════════════════════════════════════════════════════════════════════════
# PATENTES DISPONIBLES (sabana_pedimentos)
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=600)
def _patentes_disponibles_pg() -> list[dict]:
    """Carga combinaciones únicas patente/aduana_despacho desde sabana_pedimentos."""
    try:
        df = query_pg("""
            SELECT DISTINCT patente, aduana_despacho
            FROM sabana_pedimentos
            WHERE patente IS NOT NULL AND patente != ''
              AND aduana_despacho IS NOT NULL AND aduana_despacho != ''
            ORDER BY patente, aduana_despacho
        """)
        opciones = [{"valor": "TODAS", "display": "🌍 TODAS"}]
        for _, row in df.iterrows():
            pat = str(row["patente"]).strip()
            adu = str(row["aduana_despacho"]).strip()
            opciones.append({"valor": f"{pat}|{adu}", "display": f"{pat} - {adu}"})
        return opciones
    except Exception:
        return [{"valor": "TODAS", "display": "🌍 TODAS"}]


# ══════════════════════════════════════════════════════════════════════════════
# CARGA DE DATOS
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300)
def _cargar_raw(f_ini: date, f_fin: date, tipo_op: str,
                patentes_sel: tuple = ("TODAS",)) -> pd.DataFrame:
    """Query PostgreSQL con parametros bind. Filtra tipo_op y patente/aduana en SQL."""
    sql = """
        SELECT
            referencia, pedimento, patente, aduana,
            cliente, clave_pedimento, tipo_operacion,
            medio_transporte, contenedores, tipo_contenedor,
            fecha_revalidacion, fecha_arribo, fecha_pago,
            pedimento_fecha_pago, fecha_cuenta_gastos, fecha_contabilidad
        FROM cumplimiento_pedimentos
        WHERE pedimento_fecha_pago BETWEEN :f_ini AND :f_fin
    """
    params: dict = {"f_ini": f_ini, "f_fin": f_fin}
    if tipo_op in ("Importacion", "Importación"):
        sql += " AND tipo_operacion = :tipo_op"
        params["tipo_op"] = "I"
    elif tipo_op in ("Exportacion", "Exportación"):
        sql += " AND tipo_operacion = :tipo_op"
        params["tipo_op"] = "E"

    if patentes_sel and "TODAS" not in patentes_sel:
        condiciones = []
        for item in patentes_sel:
            if " - " in item:
                # formato "3740 - AEROPUERTO CD. DE MEXICO, D.F."
                pat, adu = item.split(" - ", 1)
                adu_esc = adu.replace("'", "''")
                condiciones.append(f"(patente = '{pat.strip()}' AND aduana = '{adu_esc}')")
            elif item.strip():
                # solo patente sin aduana
                pat_esc = item.strip().replace("'", "''")
                condiciones.append(f"patente = '{pat_esc}'")
        if condiciones:
            sql += " AND (" + " OR ".join(condiciones) + ")"

    sql += " ORDER BY pedimento_fecha_pago DESC"

    try:
        with get_pg_engine().connect() as conn:
            return pd.read_sql(sql_text(sql), conn, params=params)
    except Exception as e:
        st.error(f"Error PostgreSQL: {e}")
        return pd.DataFrame()


def _procesar(df: pd.DataFrame, tipo_rep: str) -> pd.DataFrame:
    """Calcula columnas derivadas: transporte, fechas, dias, meta, cumplimiento, mes."""
    fecha_cols = ["fecha_revalidacion", "fecha_arribo", "fecha_pago",
                  "pedimento_fecha_pago", "fecha_cuenta_gastos", "fecha_contabilidad"]
    for col in fecha_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    df["transporte_real"] = df.apply(
        lambda r: clasificar_transporte(
            r["medio_transporte"], r["contenedores"], r["tipo_contenedor"]), axis=1)

    if tipo_rep == "Reporte Operativo":
        df["param_fecha_inicio"] = df.apply(
            lambda r: obtener_fecha_mas_reciente(
                r["fecha_revalidacion"], r["fecha_arribo"]), axis=1)
        df["param_fecha_fin"] = df["fecha_pago"]
    else:
        df["param_fecha_inicio"] = df["fecha_contabilidad"]
        df["param_fecha_fin"] = df["fecha_cuenta_gastos"]

    df["dias_transcurridos"] = df.apply(
        lambda r: dias_habiles_oga(r["param_fecha_inicio"], r["param_fecha_fin"]), axis=1)
    df["meta_aplicada"] = df.apply(
        lambda r: meta_dinamica(
            {
                "Transporte_Real": r.get("transporte_real", r.get("transporte", "")),
                "Tipo Operación":  r.get("tipo_operacion", ""),
                "Patente":         str(r.get("patente", "")).strip(),
            },
            tipo_rep), axis=1)

    df = df.dropna(subset=["dias_transcurridos"]).copy()
    df["dias_transcurridos"] = df["dias_transcurridos"].astype(int)
    df["Cumple"] = df.apply(
        lambda r: "SI CUMPLE" if r["dias_transcurridos"] <= r["meta_aplicada"]
        else "NO CUMPLE", axis=1)

    # Mes en español para display y Mes_Num para ordenamiento
    df[["Mes", "Mes_Num"]] = df["pedimento_fecha_pago"].apply(
        lambda x: pd.Series(obtener_mes_espanol(x)))

    df["patente_aduana"] = df.apply(
        lambda r: f"{r['patente']} - {r['aduana']}"
        if pd.notna(r["patente"]) and pd.notna(r["aduana"])
        else str(r["patente"]) if pd.notna(r["patente"])
        else "SIN PATENTE", axis=1)

    return df


# ══════════════════════════════════════════════════════════════════════════════
# EXPORTACION PDF
# ══════════════════════════════════════════════════════════════════════════════

_ASSETS = os.path.join(os.path.dirname(__file__), "../../../assets")


def _generar_pdf(df: pd.DataFrame, tipo_rep: str, tipo_op: str,
                 f_ini: date, f_fin: date,
                 fig_bar=None, fig_pie=None) -> bytes:
    from fpdf import FPDF

    # ── Exportar graficas: kaleido -> matplotlib fallback ─────────────────────
    tmp_files: list[str] = []
    img_bar_path = img_pie_path = None

    def _try_kaleido(fig, w, h):
        try:
            return fig.to_image(format="png", width=w, height=h, scale=1.5)
        except Exception:
            return None

    def _mpl_bar(df):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(9, 4))
        grp = df.groupby(["Mes", "Cumple"]).size().unstack(fill_value=0)
        clr_map = {"SI CUMPLE": "#2ecc71", "NO CUMPLE": "#e74c3c"}
        cols = [c for c in ["SI CUMPLE", "NO CUMPLE"] if c in grp.columns]
        grp[cols].plot(kind="bar", stacked=True, ax=ax, color=[clr_map[c] for c in cols])
        for container in ax.containers:
            ax.bar_label(container, fontsize=13, label_type="center", fmt="%g")
        ax.set_title("Cumplimiento por Mes", fontsize=14, fontweight="bold")
        ax.set_xlabel("Mes", fontsize=11)
        ax.set_ylabel("Operaciones", fontsize=11)
        ax.tick_params(axis="both", labelsize=11)
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=120)
        plt.close(fig)
        return buf.getvalue()

    def _mpl_pie(df):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(5, 4))
        vc = df["Cumple"].value_counts()
        clrs = [("#2ecc71" if c == "SI CUMPLE" else "#e74c3c") for c in vc.index]
        ax.pie(vc.values, labels=vc.index, colors=clrs,
               autopct="%1.1f%%",
               textprops={"fontsize": 13},
               pctdistance=0.75)
        ax.set_title("Proporción Total", fontsize=14, fontweight="bold")
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=120)
        plt.close(fig)
        return buf.getvalue()

    for fig_obj, fallback_fn, label, wh in [
        (fig_bar, _mpl_bar, "bar", (750, 400)),
        (fig_pie, _mpl_pie, "pie", (500, 400)),
    ]:
        img_bytes = (_try_kaleido(fig_obj, *wh) if fig_obj is not None else None) \
                    or fallback_fn(df)
        if img_bytes:
            tf = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            tf.write(img_bytes)
            tf.close()
            tmp_files.append(tf.name)
            if label == "bar":
                img_bar_path = tf.name
            else:
                img_pie_path = tf.name

    # ── Clase PDF (header: logo izq / nombre der, igual que reporte-sir) ──────
    class _PDF(FPDF):
        def header(self):
            logo = os.path.join(_ASSETS, "OGA-Logo01.png")
            if os.path.exists(logo):
                try:
                    self.image(logo, 10, 8, 25)
                except Exception:
                    pass
            self.set_text_color(24, 43, 73)
            self.set_font("DejaVu", "B", 14)
            self.cell(0, 8, "OCAMPO GRUPO ADUANAL", 0, 1, "R")
            self.set_font("DejaVu", "", 9)
            self.set_text_color(100, 100, 100)
            self.cell(0, 5, "Reporteador Maestro", 0, 1, "R")
            self.set_text_color(0, 0, 0)
            self.line(10, 26, 287, 26)
            self.ln(8)

        def footer(self):
            self.set_y(-15)
            self.set_font("DejaVu", "", 8)
            self.set_text_color(128, 128, 128)
            self.cell(0, 10,
                      f"Pagina {self.page_no()} — "
                      f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                      0, 0, "C")
            self.set_text_color(0, 0, 0)

    pdf = _PDF("L", "mm", "A4")
    pdf.add_font("DejaVu",  "", os.path.join(_ASSETS, "DejaVuSans.ttf"))
    pdf.add_font("DejaVu", "B", os.path.join(_ASSETS, "DejaVuSans-Bold.ttf"))
    pdf.set_auto_page_break(auto=True, margin=18)

    params_txt = ("MAX(REVALIDACION, ARRIBO) vs PAGO PEDIMENTO"
                  if tipo_rep == "Reporte Operativo"
                  else "FE CONTABILIDAD vs FECHAS CUENTAS DE GASTOS")
    total     = len(df)
    cumplidas = (df["Cumple"] == "SI CUMPLE").sum()
    pct       = cumplidas / total * 100 if total > 0 else 0

    # ── Pagina 1: titulo + subtitulo + KPIs + graficas ────────────────────────
    pdf.add_page()
    pdf.set_y(34)
    pdf.set_font("DejaVu", "B", 16)
    pdf.set_text_color(24, 43, 73)
    pdf.cell(0, 10, "REPORTE DE CUMPLIMIENTO", 0, 1, "C")
    pdf.set_font("DejaVu", "B", 11)
    pdf.set_text_color(26, 115, 232)
    tipo_rep_clean = tipo_rep.replace("Reporte ", "").upper()
    pdf.cell(0, 7, f"{tipo_rep_clean} — {tipo_op.upper()}", 0, 1, "C")
    pdf.set_font("DejaVu", "", 9)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 5, f"PARAMETROS: {params_txt} | Rango: {f_ini} -> {f_fin}", 0, 1, "C")
    pdf.cell(0, 5,
             f"Generado el {datetime.now().strftime('%d/%m/%Y a las %H:%M')}",
             0, 1, "C")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    pdf.set_font("DejaVu", "B", 10)
    pdf.set_fill_color(245, 245, 245)
    for lbl in [f"TOTAL: {total}", f"CUMPLIDAS: {cumplidas}",
                f"NO CUMPLIDAS: {total - cumplidas}", f"% CUMPLIMIENTO: {pct:.1f}%"]:
        pdf.cell(60, 10, lbl, 1, 0, "C", True)
    pdf.ln()
    pdf.ln(4)

    y_graf = pdf.get_y()
    if img_bar_path:
        try:
            pdf.image(img_bar_path, x=15,  y=y_graf, w=170, h=90)
        except Exception:
            pass
    if img_pie_path:
        try:
            pdf.image(img_pie_path, x=190, y=y_graf, w=90,  h=90)
        except Exception:
            pass

    # ── Pagina 2+: detalle por mes ────────────────────────────────────────────
    pdf.add_page()
    pdf.set_y(34)
    pdf.set_font("DejaVu", "B", 12)
    pdf.set_text_color(24, 43, 73)
    pdf.cell(0, 8, "DETALLE POR MES", 0, 1, "C")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

    HEADERS = [
        ("Patente/Aduana", 45), ("Referencia", 28), ("Cliente", 42),
        ("Transporte",     30), ("F.Inicio",   20), ("F.Fin",   20),
        ("Dias",           12), ("Meta",        12), ("Cumple",  19),
    ]
    # PROBLEMA 3 — guardar Mes si no existe
    if "Mes" not in df.columns:
        df["Mes"] = pd.to_datetime(df["pedimento_fecha_pago"]).dt.strftime("%B %Y").str.upper()

    # PROBLEMA 1 — sort seguro con columnas que sí existen
    sort_cols = [c for c in ["Mes", "aduana", "pedimento"] if c in df.columns]
    df_sorted = df.sort_values(sort_cols) if sort_cols else df.copy()

    for mes in df_sorted["Mes"].unique():
        pdf.set_font("DejaVu", "B", 10)
        pdf.set_fill_color(200, 215, 245)
        pdf.cell(0, 8, f"MES: {mes.upper()}", 0, 1, "L", True)
        pdf.set_font("DejaVu", "B", 7)
        pdf.set_fill_color(230, 235, 245)
        for h, w in HEADERS:
            pdf.cell(w, 6, h, 1, 0, "C", True)
        pdf.ln()
        pdf.set_font("DejaVu", "", 7)
        # PROBLEMA 2 — acceso seguro con .get(); nombres reales de _procesar()
        for _, r in df_sorted[df_sorted["Mes"] == mes].iterrows():
            fi = r.get("param_fecha_inicio")
            ff = r.get("param_fecha_fin")
            pat = (str(r.get("patente_aduana", "")) or
                   f"{r.get('patente', '')} - {r.get('aduana', '')}").strip(" -")
            ref = str(r.get("referencia", "") or r.get("pedimento", ""))
            cli = str(r.get("cliente", ""))
            trp = str(r.get("transporte_real", "") or r.get("transporte", ""))
            dias = str(r.get("dias_transcurridos", 0))
            meta = str(r.get("meta_aplicada", 0))
            pdf.cell(45, 5, pat[:38], 1, 0, "L")
            pdf.cell(28, 5, ref[:22], 1, 0, "C")
            pdf.cell(42, 5, cli[:35], 1, 0, "L")
            pdf.cell(30, 5, trp[:24], 1, 0, "C")
            pdf.cell(20, 5, fi.strftime("%d/%m/%y") if pd.notna(fi) else "N/A", 1, 0, "C")
            pdf.cell(20, 5, ff.strftime("%d/%m/%y") if pd.notna(ff) else "N/A", 1, 0, "C")
            pdf.cell(12, 5, dias, 1, 0, "C")
            pdf.cell(12, 5, meta, 1, 0, "C")
            if r.get("Cumple") == "SI CUMPLE":
                pdf.set_text_color(0, 128, 0)
            else:
                pdf.set_text_color(190, 0, 0)
            pdf.cell(19, 5, r["Cumple"], 1, 1, "C")
            pdf.set_text_color(0, 0, 0)
        pdf.ln(3)

    for f in tmp_files:
        try:
            os.remove(f)
        except Exception:
            pass

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
# EXPORTACION EXCEL
# ══════════════════════════════════════════════════════════════════════════════

def _generar_excel(df: pd.DataFrame, img_bar: bytes | None,
                   img_pie: bytes | None, reglas: str) -> bytes:
    cols_export = ["Mes", "aduana", "pedimento", "cliente", "transporte_real",
                   "param_fecha_inicio", "param_fecha_fin",
                   "dias_transcurridos", "meta_aplicada", "Cumple"]
    df_ex = df[[c for c in cols_export if c in df.columns]].copy()
    for col in ["param_fecha_inicio", "param_fecha_fin"]:
        if col in df_ex.columns:
            df_ex[col] = df_ex[col].dt.strftime("%d/%m/%Y")
    sort_cols = [c for c in ["fecha_pago", "aduana", "pedimento"] if c in df_ex.columns]
    if sort_cols:
        df_ex = df_ex.sort_values(sort_cols)

    output = io.BytesIO()
    tmp_files: list[str] = []
    try:
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            wb = writer.book

            header_fmt = wb.add_format({
                "bold": True, "bg_color": "#1a73e8",
                "font_color": "white", "border": 1,
            })
            verde_fmt = wb.add_format({"bg_color": "#d4edda"})
            rojo_fmt  = wb.add_format({"bg_color": "#f8d7da"})

            # ── Hoja de graficos ───────────────────────────────────────────
            ws_graf = wb.add_worksheet("Graficos")
            ws_graf.write(0, 0, "REGLAS APLICADAS:")
            ws_graf.write(1, 0, reglas)
            for img_data, cell in [(img_bar, "C5"), (img_pie, "C28")]:
                if img_data:
                    try:
                        tf = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                        tf.write(img_data); tf.flush(); tf.close()
                        tmp_files.append(tf.name)
                        ws_graf.insert_image(cell, tf.name, {"x_scale": 0.7, "y_scale": 0.7})
                    except Exception:
                        pass

            # ── Hoja principal con formatos ──────────────────────────────────
            df_ex.to_excel(writer, sheet_name="Cumplimiento", index=False)
            ws = writer.sheets["Cumplimiento"]
            for col_num, value in enumerate(df_ex.columns):
                ws.write(0, col_num, value, header_fmt)
                ws.set_column(col_num, col_num, 18)
            for row_num in range(1, len(df_ex) + 1):
                cumple = str(df_ex.iloc[row_num - 1].get("Cumple", ""))
                fmt = verde_fmt if cumple == "SI CUMPLE" else rojo_fmt
                for col_num in range(len(df_ex.columns)):
                    ws.write(row_num, col_num, df_ex.iloc[row_num - 1, col_num], fmt)

            # ── Hojas por mes ──────────────────────────────────────────────
            meses_ordenados = (df.sort_values("Mes_Num")["Mes"].unique()
                               if "Mes_Num" in df.columns
                               else df["Mes"].unique())
            for mes in meses_ordenados:
                sheet = mes[:31]
                df_m = df_ex[df_ex["Mes"] == mes].drop(columns=["Mes"], errors="ignore")
                df_m.to_excel(writer, sheet_name=sheet, startrow=1, index=False)
                ws_m = writer.sheets[sheet]
                ws_m.write(0, 0, f"MES: {mes.upper()} — {reglas}")
                for col_num, value in enumerate(df_m.columns):
                    ws_m.write(1, col_num, value, header_fmt)
                    ws_m.set_column(col_num, col_num, 18)

        result = output.getvalue()
    except Exception as e:
        st.error(f"Error generando Excel: {e}")
        result = io.BytesIO().getvalue()
    finally:
        for f in tmp_files:
            try:
                os.remove(f)
            except Exception:
                pass
    return result


# ══════════════════════════════════════════════════════════════════════════════
# RENDER PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def render_cumplimiento():
    def _ir_inicio():
        st.session_state.vista = "inicio"

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.button("← Volver al menu", on_click=_ir_inicio, use_container_width=True)
        st.header("Filtros")

        # 1. Patente / Aduana
        hoy = date.today()
        primer_dia = date(hoy.year, hoy.month, 1)

        opciones = _patentes_disponibles_pg()
        opciones_display = [o["display"] for o in opciones]
        opciones_valores = [o["valor"]   for o in opciones]

        sel_display = st.multiselect(
            "Patente / Aduana",
            options=opciones_display,
            default=["🌍 TODAS"],
            key="cum_patentes",
        )

        if not sel_display or any("TODAS" in s for s in sel_display):
            patentes_sel = ["TODAS"]
        else:
            patentes_sel = [opciones_valores[opciones_display.index(s)]
                            for s in sel_display]

        st.divider()

        # 2. Tipo de reporte
        tipo_rep = st.radio(
            "Tipo de reporte",
            ["Reporte Operativo", "Reporte Administrativo"],
            key="cum_tipo_rep",
        )
        # 3. Tipo de operacion
        tipo_op = st.radio(
            "Tipo de operacion",
            ["Todos", "Importación", "Exportación"],
            key="cum_tipo_op",
        )

        # 4. Rango de fechas
        fecha_ini = st.date_input("Desde", value=primer_dia,
                                  min_value=date(2020, 1, 1), max_value=hoy,
                                  key="cum_f1")
        fecha_fin = st.date_input("Hasta", value=hoy,
                                  min_value=fecha_ini, max_value=hoy,
                                  key="cum_f2")

        cliente_filtro = st.text_input(
            "Cliente (contiene)", placeholder="Ej: HIROTEC, SADABU", key="cum_cli")

        st.markdown("---")
        st.caption(
            "Filtros ETL: Solo pagados · "
            "Excluye V1/R1/V5/F4/F5/RC/A3"
        )
        generar = st.button(
            "🔍 Generar Reporte",
            type="primary",
            use_container_width=True,
        )

    # ── Hash de filtros: limpiar session_state si cambiaron ──────────────────
    filtros_hash = hashlib.md5(
        f"{sorted(patentes_sel)}{tipo_rep}{tipo_op}{fecha_ini}{fecha_fin}{cliente_filtro}".encode()
    ).hexdigest()

    if st.session_state.get("filtros_hash") != filtros_hash:
        st.session_state.pop("df_cumplimiento", None)
        st.session_state.pop("params_cumplimiento", None)

    if "df_cumplimiento" in st.session_state:
        st.sidebar.info("📊 Reporte generado. Cambia filtros y presiona Generar para actualizar.")

    # ── Carga y procesamiento ─────────────────────────────────────────────────
    if generar or "df_cumplimiento" in st.session_state:
        if generar:
            _logger.info(
                f"[CUMPLIMIENTO] Generando — patentes_sel={patentes_sel} "
                f"tipo_op={tipo_op} tipo_rep={tipo_rep} {fecha_ini}→{fecha_fin} "
                f"cliente='{cliente_filtro}'"
            )
            df_raw = _cargar_raw(fecha_ini, fecha_fin, tipo_op, tuple(patentes_sel))
            _logger.info(f"[CUMPLIMIENTO] _cargar_raw devolvió {len(df_raw)} filas")
            if df_raw.empty:
                st.warning("Sin datos para el rango seleccionado.")
                st.session_state.pop("df_cumplimiento", None)
                return
            df = _procesar(df_raw.copy(), tipo_rep)
            if cliente_filtro.strip():
                df = df[df["cliente"].str.contains(
                    cliente_filtro.strip(), case=False, na=False)]
            _logger.info(f"[CUMPLIMIENTO] df final: {len(df)} filas tras filtros")
            st.session_state["df_cumplimiento"] = df
            st.session_state["filtros_hash"]    = filtros_hash
            st.session_state["params_cumplimiento"] = {
                "tipo_rep": tipo_rep, "tipo_op": tipo_op,
                "f_ini": fecha_ini, "f_fin": fecha_fin,
            }
        df     = st.session_state.get("df_cumplimiento", pd.DataFrame())
        params = st.session_state.get("params_cumplimiento", {})
        tipo_rep  = params.get("tipo_rep",  tipo_rep)
        tipo_op   = params.get("tipo_op",   tipo_op)
        fecha_ini = params.get("f_ini", fecha_ini)
        fecha_fin = params.get("f_fin", fecha_fin)
        if df.empty:
            st.warning("Sin registros con los filtros aplicados.")
            return
    else:
        return

    # ── Encabezado ────────────────────────────────────────────────────────────
    if tipo_rep == "Reporte Operativo":
        subtitulo = "PARAMETROS: MAX(REVALIDACION, ARRIBO) vs PAGO PEDIMENTO"
        reglas = "Operativo: MAX(Revalidacion, Arribo) -> Pago Pedimento | Tiempo minimo (70%)"
    else:
        subtitulo = "PARAMETROS: FECHA CONTA vs FACTURACION (CUENTAS GASTOS)"
        reglas = "Administrativo: Cierre (FE Conta) -> Facturacion CGA | Tiempo minimo (70%)"

    st.title("Reporte de Cumplimiento")
    st.markdown(f"**{tipo_rep} — {tipo_op}** · {subtitulo}")
    st.caption(f"Fuente: data mart PostgreSQL | Rango: {fecha_ini} -> {fecha_fin}")
    st.divider()

    # ── KPIs ──────────────────────────────────────────────────────────────────
    total        = len(df)
    cumplidas    = (df["Cumple"] == "SI CUMPLE").sum()
    no_cumplidas = total - cumplidas
    pct          = cumplidas / total * 100 if total > 0 else 0

    # Deltas: mes actual del rango vs mes anterior
    mes_actual = f_fin.strftime("%Y-%m")
    if f_ini.month == 1:
        mes_ant = date(f_ini.year - 1, 12, 1).strftime("%Y-%m")
    else:
        mes_ant = date(f_ini.year, f_ini.month - 1, 1).strftime("%Y-%m")

    df["Mes_str"] = pd.to_datetime(df["fecha_pago"]).dt.strftime("%Y-%m")
    df_act = df[df["Mes_str"] == mes_actual]
    df_ant = df[df["Mes_str"] == mes_ant]

    def _pct_cumple(d):
        return round((d["Cumple"] == "SI CUMPLE").sum() / len(d) * 100, 1) if len(d) > 0 else None

    pct_act = _pct_cumple(df_act)
    pct_ant = _pct_cumple(df_ant)
    total_ant  = len(df_ant) if len(df_ant) > 0 else None
    cumple_ant = int((df_ant["Cumple"] == "SI CUMPLE").sum()) if len(df_ant) > 0 else None

    delta_pct = (f"{round(pct_act - pct_ant, 1):+.1f}% vs mes anterior"
                 if pct_act is not None and pct_ant is not None else None)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📋 Total Operaciones", f"{total:,}",
              delta=f"{total - total_ant:+d} vs mes anterior" if total_ant else None)
    c2.metric("✅ Cumplidas", f"{cumplidas:,}",
              delta=f"{cumplidas - cumple_ant:+d} vs mes anterior" if cumple_ant else None)
    c3.metric("❌ No Cumplidas", f"{no_cumplidas:,}",
              delta=(f"{no_cumplidas - (total_ant - cumple_ant):+d} vs mes anterior"
                     if total_ant else None),
              delta_color="inverse")
    c4.metric("🎯 % Cumplimiento", f"{pct:.1f}%",
              delta=delta_pct, delta_color="normal")

    st.divider()

    # ── Preparar graficas ─────────────────────────────────────────────────────
    df_g = (df.groupby(["Mes_Num", "Mes", "Cumple"])
              .size().reset_index(name="N"))
    df_tot = (df.groupby(["Mes_Num", "Mes"])
                .size().reset_index(name="Total"))
    df_g = df_g.merge(df_tot, on=["Mes_Num", "Mes"])
    df_g["Etiqueta"] = df_g.apply(
        lambda r: f"{r['N']} ({r['N']/r['Total']*100:.1f}%)", axis=1)

    fig_bar = px.bar(
        df_g.sort_values("Mes_Num"), x="Mes", y="N", color="Cumple",
        text="Etiqueta", barmode="stack",
        color_discrete_map={"SI CUMPLE": "#2ecc71", "NO CUMPLE": "#e74c3c"},
        title="Cumplimiento Mensual",
    )
    fig_bar.update_traces(textposition="inside", textfont_size=14)
    fig_bar.update_layout(
        paper_bgcolor="rgba(255,255,255,1)",
        plot_bgcolor="rgba(255,255,255,1)",
        xaxis_title="Mes", yaxis_title="Operaciones",
        margin=dict(t=60, l=60, r=30, b=50),
    )

    df_pie_data = df.groupby("Cumple").size().reset_index(name="N")
    fig_pie = px.pie(
        df_pie_data, names="Cumple", values="N",
        color="Cumple",
        color_discrete_map={"SI CUMPLE": "#2ecc71", "NO CUMPLE": "#e74c3c"},
        title="Proporcion Total",
    )
    fig_pie.update_traces(textfont_size=16)
    fig_pie.update_layout(
        paper_bgcolor="rgba(255,255,255,1)",
        plot_bgcolor="rgba(255,255,255,1)",
        margin=dict(t=60, l=30, r=30, b=30),
    )

    # img_bar/img_pie para Excel (kaleido o None)
    try:
        img_bar = fig_bar.to_image(format="png", width=1200, height=600)
        img_pie = fig_pie.to_image(format="png", width=800,  height=600)
    except Exception:
        img_bar = img_pie = None

    # ── Botones de descarga ───────────────────────────────────────────────────
    st.markdown("### Centro de Descargas")
    col_pdf, col_xls = st.columns(2)
    with col_pdf:
        pdf_bytes = _generar_pdf(df, tipo_rep, tipo_op, fecha_ini, fecha_fin,
                                 fig_bar=fig_bar, fig_pie=fig_pie)
        st.download_button(
            "Descargar PDF",
            pdf_bytes,
            f"cumplimiento_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            "application/pdf",
            use_container_width=True,
        )
    with col_xls:
        xls_bytes = _generar_excel(df, img_bar, img_pie, reglas)
        st.download_button(
            "Descargar Excel",
            xls_bytes,
            f"cumplimiento_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    st.divider()

    # ── Graficas lado a lado ──────────────────────────────────────────────────
    col1, col2 = st.columns([2, 1])
    with col1:
        st.plotly_chart(fig_bar, use_container_width=True)
    with col2:
        st.plotly_chart(fig_pie, use_container_width=True)

    st.divider()

    # ── Detalle por mes con expanders ─────────────────────────────────────────
    st.subheader("Detalle por mes")
    cols_show = ["pedimento", "pedimento_fecha_pago", "aduana", "tipo_operacion",
                 "cliente", "transporte_real", "dias_transcurridos", "meta_aplicada", "Cumple"]

    for mes_num in sorted(df["Mes_Num"].unique()):
        df_m = df[df["Mes_Num"] == mes_num].copy()
        mes_label = df_m["Mes"].iloc[0]
        total_m   = len(df_m)
        cumple_m  = (df_m["Cumple"] == "SI CUMPLE").sum()
        pct_m     = cumple_m / total_m * 100 if total_m > 0 else 0

        with st.expander(
            f"{mes_label} — {total_m} operaciones | "
            f"{cumple_m} cumplidas ({pct_m:.1f}%)"
        ):
            df_show = df_m[[c for c in cols_show if c in df_m.columns]].sort_values(
                "pedimento_fecha_pago", ascending=False)

            def _color_rows(row):
                color = "#d1e7dd" if row["Cumple"] == "SI CUMPLE" else "#f8d7da"
                return [f"background-color: {color}"] * len(row)

            st.dataframe(
                df_show.style.apply(_color_rows, axis=1),
                use_container_width=True,
                height=400,
                hide_index=True,
            )
            st.caption(
                f"Cumplidas: {cumple_m} | "
                f"No cumplidas: {total_m - cumple_m} | "
                f"{pct_m:.1f}%"
            )
