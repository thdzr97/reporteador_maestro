import streamlit as st
import pandas as pd
import numpy as np
import sys
import os
import io
from datetime import datetime, date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from src.etl.conexion import query_pg
from src.etl.calculos_sir import (
    dias_habiles_oga,
    obtener_fecha_mas_reciente,
    clasificar_transporte,
    meta_dinamica,
)

st.set_page_config(
    page_title="Reporteador Maestro — Ocampo GA",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

if "vista" not in st.session_state:
    st.session_state.vista = "inicio"


def ir_a(vista):
    st.session_state.vista = vista


# ══════════════════════════════════════════════════════════════════════
# VISTA: INICIO
# ══════════════════════════════════════════════════════════════════════
def vista_inicio():
    import base64 as _b64

    st.markdown("""
<style>
.main .block-container { padding-top: 0 !important; max-width: 1200px; }
.rm-header {
    text-align: center;
    padding: 15px;
    background: linear-gradient(135deg, #1a73e8 0%, #0d47a1 100%);
    border-radius: 15px;
    margin-bottom: 30px;
    color: white;
}
.rm-header h1 { color: white; font-size: 2rem; font-weight: 700; margin: 0 0 6px 0; }
.rm-header p  { color: rgba(255,255,255,0.85); font-size: 1rem; margin: 0; }
.rm-section-title {
    color: #212529; font-size: 1.3rem; font-weight: 600;
    margin-bottom: 20px; padding-left: 4px;
}
.rm-card {
    background: #f8f9fa;
    border: 1px solid #e9ecef;
    border-radius: 12px;
    padding: 24px 20px 20px 20px;
    text-align: center;
    min-height: 200px;
    transition: all 0.2s;
    cursor: pointer;
}
.rm-card:hover {
    border-color: #1a73e8;
    box-shadow: 0 4px 16px rgba(26,115,232,0.15);
    transform: translateY(-2px);
}
.rm-card.disabled { opacity: 0.5; cursor: not-allowed; }
.rm-card-icon  { font-size: 2.5rem; margin-bottom: 12px; }
.rm-card-title { color: #1a73e8; font-size: 1rem; font-weight: 700; margin-bottom: 8px; line-height: 1.3; }
.rm-card-desc  { color: #6c757d; font-size: 0.82rem; line-height: 1.5; }
.rm-badge { display: inline-block; border-radius: 20px; padding: 3px 10px; font-size: 0.72rem; margin-top: 12px; font-weight: 600; }
.rm-badge.live { background: rgba(25,135,84,0.1); color: #198754; border: 1px solid rgba(25,135,84,0.3); }
.rm-badge.soon { background: #f8f9fa; color: #6c757d; border: 1px solid #dee2e6; }
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

    logo_path = '/var/www/html/ocmx/reporteador-maestro/assets/OGA-Logo01.png'
    logo_b64 = ""
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as _f:
            logo_b64 = _b64.b64encode(_f.read()).decode()

    if logo_b64:
        st.markdown(f"""
<div class="rm-header">
    <img src="data:image/png;base64,{logo_b64}"
         style="height:50px; margin-bottom:8px;
                filter:brightness(0) invert(1);">
    <h2 style="margin:0; color:white; font-size:1.6rem; font-weight:700;">
        OCAMPO GRUPO ADUANAL
    </h2>
    <p style="margin:0; opacity:0.85; font-size:0.95rem;">
        Reporteador Maestro · Área de Nuevas Tecnologías
    </p>
</div>
""", unsafe_allow_html=True)
    else:
        st.markdown("""
<div class="rm-header">
    <h2 style="margin:0; color:white; font-size:1.6rem; font-weight:700;">
        🏛️ OCAMPO GRUPO ADUANAL
    </h2>
    <p style="margin:0; opacity:0.85; font-size:0.95rem;">
        Reporteador Maestro · Área de Nuevas Tecnologías
    </p>
</div>
""", unsafe_allow_html=True)

    st.markdown('<p class="rm-section-title">📋 Selecciona el reporte</p>',
                unsafe_allow_html=True)

    REPORTES = [
        {
            "icon": "✅", "titulo": "Reporte de Cumplimiento",
            "desc": "Indicadores operativos y administrativos por aduana, tipo de operación y rango de fechas.",
            "live": True, "vista": "cumplimiento", "btn": "Ver Reporte",
        },
        {
            "icon": "📋", "titulo": "Score Card",
            "desc": "Balanced Score Card por sucursal y etapa: En Tráfico, Administrativo, Cierre.",
            "live": True, "vista": "scorecard_v1", "btn": "Ver Score Card",
        },
        {
            "icon": "📄", "titulo": "Sábana de Pedimentos",
            "desc": "Reporte padre — ciclo completo de referencias: ejecutivo, estatus, honorarios y observaciones.",
            "live": True, "vista": "sabana", "btn": "Ver Sábana",
        },
        {
            "icon": "📈", "titulo": "Score Card — KPIs Ejecutivo",
            "desc": "KPIs por ejecutivo: cumplimiento de calidad, días promedio y saldo pendiente.",
            "live": False,
        },
        {
            "icon": "📁", "titulo": "Mis Reportes",
            "desc": "Reportes guardados personalizados. Crea y versiona vistas con tus filtros preferidos.",
            "live": False,
        },
        {
            "icon": "💰", "titulo": "Reporte Financiero",
            "desc": "Facturación, pagos y cobranza por cliente y periodo.",
            "live": False,
        },
    ]

    cols = st.columns(3)
    for i, r in enumerate(REPORTES):
        with cols[i % 3]:
            badge = ('<span class="rm-badge live">● En vivo</span>'
                     if r["live"]
                     else '<span class="rm-badge soon">Próximamente</span>')
            st.markdown(f"""
<div class="rm-card {'disabled' if not r['live'] else ''}">
    <div class="rm-card-icon">{r['icon']}</div>
    <div class="rm-card-title">{r['titulo']}</div>
    <div class="rm-card-desc">{r['desc']}</div>
    {badge}
</div>
""", unsafe_allow_html=True)
            if r["live"]:
                st.button(r["btn"], key=f"btn_{i}",
                          on_click=ir_a, args=(r["vista"],),
                          use_container_width=True)
            else:
                st.button("Próximamente", key=f"btn_{i}",
                          disabled=True, use_container_width=True)

    st.markdown("""
<div style="text-align:center; color:#6c757d; font-size:0.78rem;
            margin-top:40px; padding-top:16px; border-top:1px solid #dee2e6;">
    Reporteador Maestro v0.3 · Nuevas Tecnologías · Ocampo Grupo Aduanal
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# VISTA: CUMPLIMIENTO
# ══════════════════════════════════════════════════════════════════════
from src.canales.streamlit.cumplimiento import render_cumplimiento


# ══════════════════════════════════════════════════════════════════════
# VISTA: SÁBANA DE PEDIMENTOS
# ══════════════════════════════════════════════════════════════════════
def vista_sabana():
    st.sidebar.button("← Volver al menú", on_click=ir_a, args=("inicio",))
    st.title("Sábana de Pedimentos")
    st.caption("Fuente: data mart PostgreSQL (ETL desde SIRADMIN)")
    st.sidebar.header("Filtros")

    hoy = date.today()
    primer_dia_mes = hoy.replace(day=1)
    col_f1, col_f2 = st.sidebar.columns(2)
    with col_f1:
        fecha_inicio = st.date_input("Desde", value=primer_dia_mes, key="sab_f1")
    with col_f2:
        fecha_fin = st.date_input("Hasta", value=hoy, key="sab_f2")

    @st.cache_data(ttl=120)
    def cargar_sabana(f_ini, f_fin):
        return query_pg(f"""
            SELECT referencia, fecha_apertura, fecha_pago, ejecutivo, cliente,
                   aduana_despacho, tipo_operacion, status_referencia,
                   honorarios, total_cga, primera_seleccion, segunda_seleccion,
                   valor_aduana, cantidad_facturas, cantidad_partidas,
                   fracciones, observaciones
            FROM sabana_pedimentos
            WHERE fecha_pago >= '{f_ini}' AND fecha_pago <= '{f_fin}'
            ORDER BY fecha_pago DESC
        """)

    df = cargar_sabana(fecha_inicio, fecha_fin)
    if df.empty:
        st.warning("Sin datos para el rango seleccionado.")
        return

    ejecutivos = ["Todos"] + sorted(df["ejecutivo"].dropna().unique().tolist())
    ejecutivo_sel = st.sidebar.selectbox("Ejecutivo", ejecutivos, key="sab_ej")

    cliente_filtro = st.sidebar.text_input("Cliente (contiene)", "", key="sab_cli")

    aduanas = ["TODAS"] + sorted(df["aduana_despacho"].dropna().unique().tolist())
    aduanas_sel = st.sidebar.multiselect("Aduana", aduanas, default=["TODAS"], key="sab_adu")

    tipo_op = st.sidebar.selectbox("Tipo de operación", ["Todos", "Importación", "Exportación"], key="sab_to")

    status_opciones = sorted(df["status_referencia"].dropna().unique().tolist())
    status_opciones = [s for s in status_opciones if s.strip()]
    status_sel = st.sidebar.multiselect("Status", status_opciones, default=[], key="sab_st")

    if st.sidebar.button("Limpiar filtros", key="sab_limpiar"):
        st.rerun()

    if ejecutivo_sel != "Todos":
        df = df[df["ejecutivo"] == ejecutivo_sel]
    if cliente_filtro.strip():
        df = df[df["cliente"].str.contains(cliente_filtro, case=False, na=False)]
    if aduanas_sel and "TODAS" not in aduanas_sel:
        df = df[df["aduana_despacho"].isin(aduanas_sel)]
    if tipo_op == "Importación":
        df = df[df["tipo_operacion"] == "I"]
    elif tipo_op == "Exportación":
        df = df[df["tipo_operacion"] == "E"]
    if status_sel:
        df = df[df["status_referencia"].isin(status_sel)]

    if df.empty:
        st.warning("Sin datos después de aplicar filtros.")
        return

    total_refs = len(df)
    total_honorarios = df["honorarios"].sum() or 0
    total_valor_aduana = df["valor_aduana"].sum() or 0
    verdes = len(df[df["primera_seleccion"].str.lower().str.strip() == "verde"]) if "primera_seleccion" in df.columns else 0
    pct_verde = round(verdes * 100 / total_refs, 1) if total_refs > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total referencias", f"{total_refs:,}")
    c2.metric("Honorarios MXN", f"${total_honorarios:,.0f}")
    c3.metric("Valor aduana USD", f"${total_valor_aduana:,.0f}")
    c4.metric("% Verde (1a sel.)", f"{pct_verde}%")

    st.subheader("Detalle de referencias")

    cols_tabla = ["referencia", "fecha_apertura", "fecha_pago", "ejecutivo", "cliente",
                  "aduana_despacho", "tipo_operacion", "status_referencia",
                  "honorarios", "total_cga", "primera_seleccion", "segunda_seleccion",
                  "valor_aduana", "cantidad_facturas", "cantidad_partidas", "fracciones"]
    df_show = df[[c for c in cols_tabla if c in df.columns]].copy()
    df_show.columns = ["Referencia", "F. Apertura", "F. Pago", "Ejecutivo", "Cliente",
                        "Aduana", "Tipo Op", "Status",
                        "Honorarios", "Total CGA", "1a Selección", "2a Selección",
                        "Valor Aduana", "Facturas", "Partidas", "Fracciones"]

    def color_status(val):
        if not isinstance(val, str):
            return ""
        v = val.upper()
        if "CERRAD" in v or "PAGAD" in v:
            return "background-color: #d4edda; color: #155724"
        if "CANCEL" in v:
            return "background-color: #f8d7da; color: #721c24"
        if "ELABOR" in v or "ESPERA" in v:
            return "background-color: #fff3cd; color: #856404"
        return "background-color: #e2e3e5; color: #383d41"

    st.dataframe(df_show.style.map(color_status, subset=["Status"]),
                 use_container_width=True, height=600)

    with st.expander(f"Ver observaciones ({len(df[df['observaciones'].notna()]):,} registros con notas)"):
        df_obs = df[df["observaciones"].notna() & (df["observaciones"].str.strip() != "")]
        if df_obs.empty:
            st.info("Sin observaciones en los registros filtrados.")
        else:
            for _, row in df_obs[["referencia", "observaciones"]].iterrows():
                st.markdown(f"**{row['referencia']}:** {row['observaciones'][:500]}")

    st.caption(f"Mostrando {total_refs:,} referencias | Rango: {fecha_inicio} → {fecha_fin}")


# ══════════════════════════════════════════════════════════════════════
# VISTA: SCORE CARD
# ══════════════════════════════════════════════════════════════════════
def vista_scorecard():
    st.sidebar.button("← Volver al menú", on_click=ir_a, args=("inicio",))
    st.title("Score Card — KPIs por Ejecutivo")
    st.caption("Fuente: data mart PostgreSQL (ETL desde SIRADMIN)")
    st.sidebar.header("Filtros")

    anio = st.sidebar.selectbox("Año", [2026, 2025], key="sc_anio")

    @st.cache_data(ttl=120)
    def cargar_scorecard(anio_sel):
        return query_pg(f"""
            SELECT * FROM scorecard_referencias
            WHERE EXTRACT(YEAR FROM fecha_apertura) = {anio_sel}
        """)

    df = cargar_scorecard(anio)
    if df.empty:
        st.warning("Sin datos para el año seleccionado.")
        return

    ejecutivos = ["Todos"] + sorted(df["ejecutivo"].dropna().unique().tolist())
    ejecutivo_sel = st.sidebar.selectbox("Ejecutivo", ejecutivos, key="sc_ej")

    status_opciones = sorted(df["status_desc"].dropna().unique().tolist())
    status_sel = st.sidebar.multiselect("Status", status_opciones, default=[], key="sc_st")

    solo_despachados = st.sidebar.checkbox("Solo despachados", key="sc_desp")

    if ejecutivo_sel != "Todos":
        df = df[df["ejecutivo"] == ejecutivo_sel]
    if status_sel:
        df = df[df["status_desc"].isin(status_sel)]
    if solo_despachados:
        df = df[df["despachado"] == True]

    if df.empty:
        st.warning("Sin datos después de aplicar filtros.")
        return

    total_refs = len(df)
    despachadas = int(df["despachado"].sum())
    pct_despacho = round(despachadas * 100 / total_refs, 1) if total_refs > 0 else 0
    con_primera_sel = int(df["fecha_prim_sel"].notna().sum())
    saldo_total = df["saldo"].sum() or 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total referencias", f"{total_refs:,}")
    c2.metric("% Despachadas", f"{pct_despacho}%",
              delta=f"{despachadas:,} de {total_refs:,}")
    c3.metric("Con 1a selección", f"{con_primera_sel:,}")
    c4.metric("Saldo pendiente", f"${saldo_total:,.0f}")

    st.subheader("Resumen por ejecutivo")

    resumen = df.groupby("ejecutivo", dropna=False).agg(
        total_referencias=("referencia", "count"),
        despachadas=("despachado", "sum"),
        con_primera_sel=("fecha_prim_sel", lambda x: x.notna().sum()),
        con_segunda_sel=("fecha_seg_sel", lambda x: x.notna().sum()),
        honorarios=("honorarios", "sum"),
        saldo=("saldo", "sum"),
    ).reset_index()

    # Días promedio: solo referencias con dias_calidad_despacho > 0
    df_con_dias = df[pd.to_numeric(df.get("dias_calidad_despacho", pd.Series()), errors="coerce").fillna(0) > 0]
    if not df_con_dias.empty:
        dias_por_ej = (
            df_con_dias.groupby("ejecutivo")["dias_calidad_despacho"]
            .mean().round(1).rename("dias_prom_despacho")
        )
        resumen = resumen.merge(dias_por_ej, on="ejecutivo", how="left")
    else:
        resumen["dias_prom_despacho"] = None

    resumen["pct_despacho"] = resumen.apply(
        lambda r: round(r["despachadas"] / r["total_referencias"] * 100, 1)
        if r["total_referencias"] > 0 else 0.0,
        axis=1
    )

    df_resumen = resumen[["ejecutivo", "total_referencias", "despachadas", "pct_despacho",
                           "con_primera_sel", "con_segunda_sel",
                           "dias_prom_despacho", "honorarios", "saldo"]].copy()
    df_resumen.columns = ["Ejecutivo", "Total", "Despachadas", "% Desp.",
                           "1a Sel.", "2a Sel.", "Días Prom.",
                           "Honorarios", "Saldo"]
    df_resumen = df_resumen.sort_values("Total", ascending=False)
    df_resumen["Ejecutivo"] = df_resumen["Ejecutivo"].fillna("SIN ASIGNAR")

    def color_pct(val):
        try:
            v = float(val)
        except (ValueError, TypeError):
            return ""
        if v >= 90:
            return "background-color: #d4edda; color: #155724"
        if v >= 75:
            return "background-color: #fff3cd; color: #856404"
        return "background-color: #f8d7da; color: #721c24"

    st.dataframe(
        df_resumen.style
            .map(color_pct, subset=["% Desp."])
            .format({"Honorarios": "${:,.0f}", "Saldo": "${:,.0f}"}),
        use_container_width=True, height=500)

    if ejecutivo_sel != "Todos":
        st.subheader(f"Detalle — {ejecutivo_sel}")
        cols_det = ["referencia", "fecha_apertura", "status_desc",
                    "despachado", "fecha_despacho",
                    "fecha_prim_sel", "fecha_seg_sel",
                    "honorarios", "saldo", "observaciones"]
        df_det = df[[c for c in cols_det if c in df.columns]].copy()
        df_det.columns = ["Referencia", "F. Apertura", "Status",
                           "Despachado", "F. Despacho",
                           "F. 1a Sel.", "F. 2a Sel.",
                           "Honorarios", "Saldo", "Observaciones"]
        df_det = df_det.sort_values("F. Apertura", ascending=False)
        st.dataframe(df_det, use_container_width=True, height=400)

    st.caption(f"Mostrando {total_refs:,} referencias | Año: {anio}")


# ══════════════════════════════════════════════════════════════════════
# VISTA: SCORE CARD V1
# ══════════════════════════════════════════════════════════════════════
def _pdf_scorecard_v1(df_det, etapa_map, total_general, filtros_desc):
    """
    PDF Balanced Scorecard — agrupado por sucursal y etapa, con saltos de página automáticos.
    Columnas: Ref|Cliente|Pedimento|P|F.Pago|SelAle|F_E Cont|F.Cierre|TRF|ADM|CGA|Proform|Factura
    """
    from fpdf import FPDF
    import os, shutil

    FONT_DIR = "/var/www/html/ocmx/reporteador-maestro/assets"
    font_path = f"{FONT_DIR}/DejaVuSans.ttf"
    font_bold = f"{FONT_DIR}/DejaVuSans-Bold.ttf"
    os.makedirs(FONT_DIR, exist_ok=True)
    for dest, src in [
        (font_path, "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        (font_bold, "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]:
        if not os.path.exists(dest) and os.path.exists(src):
            shutil.copy2(src, dest)

    COLORES = {
        "EN TRAFICO":     {"text": (74, 144, 226),  "fill": (13, 27, 60)},
        "ADMINISTRATIVO": {"text": (232, 168, 56),   "fill": (50, 32, 0)},
        "CIERRE":         {"text": (39, 174, 96),    "fill": (8, 38, 16)},
    }
    COLS_PDF = [
        ("Ref",       26), ("Cliente",  50), ("Pedimento", 22), ("P",        8),
        ("F.Pago",    18), ("SelAle",   18), ("F_E Cont",  18), ("F.Cierre", 18),
        ("TRF",        9), ("ADM",       9), ("CGA",        9),
        ("Proform",   22), ("Factura",  22),
    ]
    total_w = sum(w for _, w in COLS_PDF)  # 257mm

    resumen_pie = (
        f"EN TRAFICO: {etapa_map['EN TRAFICO']}  |  "
        f"ADMINISTRATIVO: {etapa_map['ADMINISTRATIVO']}  |  "
        f"CIERRE: {etapa_map['CIERRE']}"
    )

    class PDF(FPDF):
        def header(self):
            self.set_font("DejaVu", "B", 14)
            self.cell(0, 8, "BALANCED SCORECARD", align="C", new_x="LMARGIN", new_y="NEXT")
            self.set_font("DejaVu", "B", 10)
            self.cell(0, 6, "OCAMPO GRUPO ADUANAL", align="C", new_x="LMARGIN", new_y="NEXT")
            self.set_font("DejaVu", "", 8)
            self.cell(0, 5, f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}  |  {filtros_desc}",
                      align="C", new_x="LMARGIN", new_y="NEXT")
            self.ln(2)

        def footer(self):
            self.set_y(-14)
            self.set_font("DejaVu", "", 7)
            self.cell(0, 5, resumen_pie, align="C", new_x="LMARGIN", new_y="NEXT")
            self.cell(0, 5,
                      f"Pág. {self.page_no()} — Reporteador Maestro · Nuevas Tecnologías",
                      align="C")

    pdf = PDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(False)
    pdf.add_font("DejaVu", "",  font_path)
    pdf.add_font("DejaVu", "B", font_bold)
    pdf.add_page()

    PAGE_H = pdf.h
    BOTTOM = 18  # espacio para footer

    def _need_break(h):
        return pdf.get_y() + h > PAGE_H - BOTTOM

    def _draw_col_headers():
        pdf.set_font("DejaVu", "B", 6.5)
        pdf.set_fill_color(30, 39, 97)
        pdf.set_text_color(202, 220, 252)
        for label, w in COLS_PDF:
            pdf.cell(w, 5.5, label, border=1, fill=True, align="C")
        pdf.ln()
        pdf.set_text_color(0, 0, 0)

    def _draw_suc_header(suc, cont=False):
        pdf.set_font("DejaVu", "B", 9)
        pdf.set_fill_color(20, 25, 60)
        pdf.set_text_color(202, 220, 252)
        label = f"  SUCURSAL: {suc.upper()}" + (" (cont.)" if cont else "")
        pdf.cell(total_w, 7, label, border=0, fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        pdf.ln(1)

    def _draw_etapa_header(etapa, cont=False):
        c = COLORES.get(etapa, {"text": (100, 100, 100), "fill": (20, 20, 20)})
        pdf.set_font("DejaVu", "B", 7)
        pdf.set_fill_color(*c["fill"])
        pdf.set_text_color(*c["text"])
        label = f"  {etapa}" + (" (cont.)" if cont else "")
        pdf.cell(total_w, 6, label, border=0, fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        _draw_col_headers()

    df_act = df_det[df_det["etapa_operacion"].isin(COLORES)].copy()
    # Excluir CIERRE con dias_cga > 5 (igual que la vista web)
    if "etapa_operacion" in df_act.columns and "dias_cga" in df_act.columns:
        df_act = df_act[~((df_act["etapa_operacion"] == "CIERRE") &
                          (df_act["dias_cga"] > 5))]
    if df_act.empty:
        pdf.set_font("DejaVu", "", 10)
        pdf.cell(0, 10, "Sin registros activos con los filtros seleccionados.",
                 new_x="LMARGIN", new_y="NEXT")
    else:
        ETAPA_ORD = {"EN TRAFICO": 1, "ADMINISTRATIVO": 2, "CIERRE": 3}
        df_act["_ord"] = df_act["etapa_operacion"].map(ETAPA_ORD).fillna(4)
        df_act = df_act.sort_values(
            ["sucursal", "_ord", "dias_adm"], ascending=[True, True, False]
        )
        cur_suc = None
        cur_etapa = None

        for _, row in df_act.iterrows():
            suc   = str(row.get("sucursal", "") or "SIN SUCURSAL").strip()
            etapa = str(row.get("etapa_operacion", ""))

            if suc != cur_suc:
                if _need_break(18):
                    pdf.add_page()
                    _draw_suc_header(suc, cont=False)
                else:
                    pdf.ln(2)
                    _draw_suc_header(suc, cont=False)
                cur_suc = suc
                cur_etapa = None

            if etapa != cur_etapa:
                if _need_break(13):
                    pdf.add_page()
                    _draw_suc_header(cur_suc, cont=True)
                cur_etapa = etapa
                _draw_etapa_header(etapa, cont=False)

            if _need_break(5.5):
                pdf.add_page()
                _draw_suc_header(cur_suc, cont=True)
                _draw_etapa_header(cur_etapa, cont=True)

            pagado = "SI" if row.get("pedimento_pagado") else "NO"
            pdf.set_font("DejaVu", "", 6.5)
            vals = [
                (str(row.get("referencia",       "") or "")[:18], 26, "L"),
                (str(row.get("cliente",          "") or "")[:32], 50, "L"),
                (str(row.get("pedimento",        "") or "")[:14], 22, "L"),
                (pagado,                                            8, "C"),
                (str(row.get("fecha_pago",       "") or "")[:10], 18, "C"),
                (str(row.get("fecha_prim_sel",   "") or "")[:10], 18, "C"),
                (str(row.get("f_e_contabilidad", "") or "")[:10], 18, "C"),
                (str(row.get("fecha_cierre_adm", "") or "")[:10], 18, "C"),
                (str(int(row.get("dias_trf", 0) or 0)),            9, "C"),
                (str(int(row.get("dias_adm", 0) or 0)),            9, "C"),
                (str(int(row.get("dias_cga", 0) or 0)),            9, "C"),
                (str(row.get("folio_proforma",   "") or "")[:14], 22, "L"),
                (str(row.get("num_fac_cga",      "") or "")[:14], 22, "L"),
            ]
            for txt, w, align in vals:
                pdf.cell(w, 5.5, txt, border=1, align=align)
            pdf.ln()

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()


def vista_scorecard_v1():
    st.sidebar.button("← Volver al menú", on_click=ir_a, args=("inicio",))
    st.sidebar.header("Balanced Score Card")

    # ── Filtros ──
    @st.cache_data(ttl=300)
    def _sucursales():
        df = query_pg("SELECT DISTINCT sucursal FROM mv_scorecard_v1_activo WHERE sucursal IS NOT NULL ORDER BY sucursal")
        return df["sucursal"].tolist() if not df.empty else []

    opciones_suc = ["TODAS"] + _sucursales()
    sucursales_sel = st.sidebar.multiselect("Sucursal", opciones_suc, default=["TODAS"], key="scv1_suc")

    ETAPAS = ["EN TRAFICO", "ADMINISTRATIVO", "CIERRE", "OTRO"]
    etapas_sel = st.sidebar.multiselect(
        "Etapa de operación",
        options=ETAPAS,
        default=ETAPAS,
        key="scv1_etapa",
    )

    # ── WHERE dinámico ──
    conds = []
    if sucursales_sel and "TODAS" not in sucursales_sel:
        s = ", ".join([f"'{x}'" for x in sucursales_sel])
        conds.append(f"sucursal IN ({s})")
    if etapas_sel and len(etapas_sel) < len(ETAPAS):
        s = ", ".join([f"'{x}'" for x in etapas_sel])
        conds.append(f"etapa_operacion IN ({s})")
    # Ocultar CIERRE con dias_cga > 5 hasta que se defina la Etapa 4
    conds.append("NOT (etapa_operacion = 'CIERRE' AND dias_cga > 5)")
    where = ("WHERE " + " AND ".join(conds)) if conds else ""

    filtros_desc = (
        ("Suc: " + ", ".join(sucursales_sel) if "TODAS" not in sucursales_sel else "Todas sucursales")
        + " | " + ", ".join(etapas_sel)
    )

    # ── Dashboard de porcentajes ──
    @st.cache_data(ttl=120)
    def _etapas(w):
        return query_pg(
            f"SELECT etapa_operacion, COUNT(*) AS total FROM scorecard_v1 {w} GROUP BY etapa_operacion"
        )

    df_et = _etapas(where)
    etapa_map = {"EN TRAFICO": 0, "ADMINISTRATIVO": 0, "CIERRE": 0, "OTRO": 0}
    if not df_et.empty:
        for _, row in df_et.iterrows():
            k = row["etapa_operacion"] if row["etapa_operacion"] in etapa_map else "OTRO"
            etapa_map[k] += int(row["total"])
    total_general = sum(etapa_map.values()) or 1

    COLORES = {
        "EN TRAFICO":     "#4A90E2",
        "ADMINISTRATIVO": "#E8A838",
        "CIERRE":         "#27AE60",
        "OTRO":           "#7F8C8D",
    }

    # ── Pre-computar datos antes de renderizar ──
    @st.cache_data(ttl=120)
    def _detalle(w):
        return query_pg(f"""
            SELECT
                referencia, cliente, pedimento, sucursal, ejecutivo,
                tipo_operacion, fecha_pago, fecha_prim_sel,
                f_e_contabilidad, fecha_cierre_adm,
                dias_trf, dias_adm, dias_cga,
                etapa_operacion, pedimento_pagado,
                folio_proforma, num_fac_cga
            FROM scorecard_v1
            {w}
            ORDER BY
                CASE etapa_operacion
                    WHEN 'EN TRAFICO'     THEN 1
                    WHEN 'ADMINISTRATIVO' THEN 2
                    WHEN 'CIERRE'         THEN 3
                    ELSE 4
                END,
                dias_adm DESC
        """)

    df = _detalle(where)

    COLS_SHOW = [
        "referencia", "cliente", "pedimento", "pedimento_pagado",
        "sucursal", "ejecutivo", "tipo_operacion",
        "fecha_pago", "fecha_prim_sel", "f_e_contabilidad", "fecha_cierre_adm",
        "dias_trf", "dias_adm", "dias_cga",
        "etapa_operacion", "folio_proforma", "num_fac_cga",
    ]
    RENAME = {
        "referencia":       "Referencia",
        "cliente":          "Cliente",
        "pedimento":        "Pedimento",
        "pedimento_pagado": "P",
        "sucursal":         "Sucursal",
        "ejecutivo":        "Ejecutivo",
        "tipo_operacion":   "Tipo Op",
        "fecha_pago":       "F. Pago",
        "fecha_prim_sel":   "F. PrimSel",
        "f_e_contabilidad": "F. Contabilidad",
        "fecha_cierre_adm": "F. Cierre",
        "dias_trf":         "Dias TRF",
        "dias_adm":         "Dias ADM",
        "dias_cga":         "Dias CGA",
        "etapa_operacion":  "Etapa",
        "folio_proforma":   "Proforma",
        "num_fac_cga":      "Num. Fac",
    }

    df_show = df[[c for c in COLS_SHOW if c in df.columns]].copy()
    df_show = df_show.rename(columns=RENAME)
    df_show["P"] = df_show["P"].map({True: "SI", False: "NO", 1: "SI", 0: "NO"})

    pdf_conds = [c for c in conds if "etapa_operacion" not in c]
    pdf_where = ("WHERE " + " AND ".join(pdf_conds)) if pdf_conds else ""

    @st.cache_data(ttl=120)
    def _pdf(pw, fd):
        df_pdf = query_pg(f"""
            SELECT referencia, cliente, pedimento, sucursal, pedimento_pagado,
                   fecha_pago, fecha_prim_sel, f_e_contabilidad, fecha_cierre_adm,
                   dias_trf, dias_adm, dias_cga, etapa_operacion,
                   folio_proforma, num_fac_cga
            FROM mv_scorecard_v1_activo
            {pw}
            ORDER BY sucursal,
                     CASE etapa_operacion
                         WHEN 'EN TRAFICO'     THEN 1
                         WHEN 'ADMINISTRATIVO' THEN 2
                         WHEN 'CIERRE'         THEN 3
                         ELSE 4
                     END,
                     dias_adm DESC
        """)
        return _pdf_scorecard_v1(df_pdf, etapa_map, total_general, fd)

    pdf_bytes = _pdf(pdf_where, filtros_desc)

    buf_xl = io.BytesIO()
    df_show.to_excel(buf_xl, index=False, engine="openpyxl")
    buf_xl.seek(0)

    # ── Render: título → métricas → barra → botones → tabla ──
    st.title("Balanced Score Card")
    st.caption("Fuente: data mart PostgreSQL · ETL desde [SIRADMIN].[dbo].[vw_sc_operacion_base]")

    c1, c2, c3, c4 = st.columns(4)
    for col, etapa in zip([c1, c2, c3, c4], COLORES):
        cnt = etapa_map[etapa]
        pct = round(cnt * 100 / total_general, 1)
        col.metric(etapa.title(), f"{cnt:,}", delta=f"{pct}%")

    segs = []
    for etapa, color in COLORES.items():
        pct = etapa_map[etapa] * 100 / total_general
        if pct > 0:
            segs.append(
                f'<div style="flex:{pct:.2f};background:{color};height:16px;border-radius:2px;margin-right:2px;" '
                f'title="{etapa}: {pct:.1f}%"></div>'
            )
    leyenda = " ".join(
        f'<span style="color:{c}">■ {e.title()}</span>'
        for e, c in COLORES.items()
    )
    st.markdown(
        f'<div style="display:flex;width:100%;margin:8px 0 2px 0;">{"".join(segs)}</div>'
        f'<div style="display:flex;gap:18px;font-size:0.77rem;color:#8B9DB5;margin-bottom:14px;">{leyenda}</div>',
        unsafe_allow_html=True,
    )

    if df.empty:
        st.warning("Sin datos para los filtros seleccionados.")
        return

    # ── Botones de descarga (encima de la tabla) ──
    col_xls, col_pdf_btn = st.columns([1, 1])
    with col_xls:
        st.download_button(
            label="📥 Descargar Excel",
            data=buf_xl,
            file_name=f"scorecard_v1_{date.today().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    with col_pdf_btn:
        st.download_button(
            label="📄 Descargar PDF",
            data=pdf_bytes,
            file_name=f"scorecard_v1_{date.today().strftime('%Y%m%d')}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    st.divider()
    st.markdown(f"### Detalle — {len(df):,} referencias")

    ESTILO_ETAPA = {
        "EN TRAFICO":     "background-color:#E8F0FE;color:#1557B0",
        "ADMINISTRATIVO": "background-color:#FEF9E7;color:#7D5A00",
        "CIERRE":         "background-color:#E9F7EF;color:#145A32",
        "OTRO":           "background-color:#F5F5F5;color:#5F5E5A",
    }

    def _cel_etapa(val):
        return ESTILO_ETAPA.get(val, "")

    def color_trf(val):
        if not isinstance(val, (int, float)) or val == 0:
            return ''
        if val <= 3:
            return 'background-color: rgba(25,135,84,0.15); color: #0a3622; font-weight:600'
        if val <= 7:
            return 'background-color: rgba(255,193,7,0.20); color: #664d03; font-weight:600'
        return 'background-color: rgba(220,53,69,0.15); color: #58151c; font-weight:600'

    def color_adm(val):
        if not isinstance(val, (int, float)) or val == 0:
            return ''
        if val <= 3:
            return 'background-color: rgba(25,135,84,0.15); color: #0a3622; font-weight:600'
        if val <= 7:
            return 'background-color: rgba(255,193,7,0.20); color: #664d03; font-weight:600'
        return 'background-color: rgba(220,53,69,0.15); color: #58151c; font-weight:600'

    def color_cga(val):
        if not isinstance(val, (int, float)) or val == 0:
            return ''
        if val <= 5:
            return 'background-color: rgba(25,135,84,0.15); color: #0a3622; font-weight:600'
        return 'background-color: rgba(220,53,69,0.15); color: #58151c; font-weight:600'

    total_filas = len(df_show)
    page_size = 500
    if total_filas > page_size:
        st.caption(
            f"Mostrando primeros {page_size} de {total_filas:,} registros. "
            "Descarga Excel para ver todos."
        )
        df_display = df_show.head(page_size)
    else:
        df_display = df_show

    st.dataframe(
        df_display.style
            .map(_cel_etapa, subset=["Etapa"])
            .map(color_trf,  subset=["Dias TRF"])
            .map(color_adm,  subset=["Dias ADM"])
            .map(color_cga,  subset=["Dias CGA"])
            .format({"Dias TRF": "{:.0f}", "Dias ADM": "{:.0f}", "Dias CGA": "{:.0f}"},
                    na_rep="—"),
        use_container_width=True,
        height=600,
    )

    st.caption(
        "Leyenda días — TRF/ADM: verde ≤3d · naranja ≤7d · rojo >7d"
    )


# ══════════════════════════════════════════════════════════════════════
# ROUTER
# ══════════════════════════════════════════════════════════════════════
vista = st.session_state.vista
if vista == "cumplimiento":
    render_cumplimiento()
elif vista == "sabana":
    vista_sabana()
elif vista == "scorecard":
    vista_scorecard()
elif vista == "mis_reportes":
    from src.canales.streamlit.mis_reportes import render_mis_reportes
    render_mis_reportes()
elif vista == "scorecard_v1":
    vista_scorecard_v1()
else:
    vista_inicio()
