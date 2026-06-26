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
    st.markdown("""
    <style>
    #MainMenu, footer, header { visibility: hidden; }
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    .rm-card {
        background: #1E2761;
        border: 1px solid rgba(202, 220, 252, 0.12);
        border-radius: 14px;
        padding: 28px 24px 20px 24px;
        transition: border-color 0.2s, transform 0.2s;
        min-height: 190px;
        display: flex; flex-direction: column; justify-content: space-between;
    }
    .rm-card:hover { border-color: rgba(202, 220, 252, 0.45); transform: translateY(-2px); }
    .rm-card.disabled { opacity: 0.45; cursor: not-allowed; }
    .rm-card-icon { font-size: 2.2rem; margin-bottom: 10px; }
    .rm-card-title { color: #CADCFC; font-size: 1.05rem; font-weight: 700; margin-bottom: 6px; }
    .rm-card-desc { color: #8B9DB5; font-size: 0.85rem; line-height: 1.5; flex-grow: 1; }
    .rm-badge { display: inline-block; border-radius: 20px; padding: 3px 11px; font-size: 0.72rem; margin-top: 14px; font-weight: 600; }
    .rm-badge.live { background: rgba(34,197,94,0.15); color: #4ADE80; border: 1px solid rgba(34,197,94,0.3); }
    .rm-badge.soon { background: rgba(202,220,252,0.08); color: #8B9DB5; border: 1px solid rgba(202,220,252,0.12); }
    .rm-header { border-bottom: 1px solid rgba(202,220,252,0.12); padding-bottom: 20px; margin-bottom: 8px; }
    .rm-title { font-size: 1.8rem; font-weight: 700; color: #CADCFC; margin: 0; }
    .rm-subtitle { color: #8B9DB5; font-size: 0.9rem; margin-top: 4px; }
    .rm-footer { margin-top: 40px; padding-top: 16px; border-top: 1px solid rgba(202,220,252,0.08); color: #4A5568; font-size: 0.78rem; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="rm-header">
        <p class="rm-title">📊 Reporteador Maestro</p>
        <p class="rm-subtitle">Ocampo Grupo Aduanal · Área de Nuevas Tecnologías · Selecciona el reporte</p>
    </div>
    """, unsafe_allow_html=True)

    REPORTES = [
        {"icon": "✅", "titulo": "Dashboard de Cumplimiento",
         "desc": "Indicadores operativos y administrativos. Filtra por aduana, tipo de operación, cliente y rango de fechas.",
         "live": True, "vista": "cumplimiento", "btn": "Ver Dashboard"},
        {"icon": "📋", "titulo": "Sábana de Pedimentos",
         "desc": "Ciclo completo de referencias: ejecutivo, estatus, honorarios, selecciones y observaciones.",
         "live": True, "vista": "sabana", "btn": "Ver Sábana"},
        {"icon": "📈", "titulo": "Score Card",
         "desc": "KPIs por ejecutivo: cumplimiento de calidad, días promedio y saldo pendiente.",
         "live": True, "vista": "scorecard", "btn": "Ver Score Card"},
        {"icon": "📁", "titulo": "Mis Reportes",
         "desc": "Reportes personalizados guardados. Crea y versiona vistas con tus filtros y columnas preferidas.",
         "live": True, "vista": "mis_reportes", "btn": "Ver Mis Reportes"},
        {"icon": "🎯", "titulo": "Score Card v1",
         "desc": "Seguimiento operativo por etapa: En Tráfico, Administrativo y Cierre. Días de aging y exportación.",
         "live": True, "vista": "scorecard_v1", "btn": "Ver Score Card v1"},
        {"icon": "💰", "titulo": "Reporte Financiero",
         "desc": "Facturación, pagos y cobranza por cliente y periodo.", "live": False},
        {"icon": "🏢", "titulo": "Reporte por Cliente",
         "desc": "Análisis detallado de cumplimiento y volumen por cliente.", "live": False},
        {"icon": "⚙️", "titulo": "Configuración",
         "desc": "Parámetros del sistema, gestión de usuarios y preferencias.", "live": False},
    ]

    cols = st.columns(3)
    for i, r in enumerate(REPORTES):
        with cols[i % 3]:
            badge = '<span class="rm-badge live">● En vivo</span>' if r["live"] else '<span class="rm-badge soon">Próximamente</span>'
            st.markdown(f"""
            <div class="rm-card {'disabled' if not r['live'] else ''}">
                <div>
                    <div class="rm-card-icon">{r['icon']}</div>
                    <div class="rm-card-title">{r['titulo']}</div>
                    <div class="rm-card-desc">{r['desc']}</div>
                </div>
                {badge}
            </div>
            """, unsafe_allow_html=True)
            if r["live"]:
                st.button(f"📊 {r['btn']}", key=f"btn_{i}", on_click=ir_a, args=(r["vista"],), use_container_width=True)
            else:
                st.button("Próximamente", key=f"btn_{i}", disabled=True, use_container_width=True)

    st.markdown("""
    <div class="rm-footer">
        Fuente: data mart PostgreSQL · ETL desde SIRADMIN cada 90 seg ·
        Reporteador Maestro v0.1 · Nuevas Tecnologías
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# VISTA: CUMPLIMIENTO
# ══════════════════════════════════════════════════════════════════════
def vista_cumplimiento():
    st.sidebar.button("← Volver al menú", on_click=ir_a, args=("inicio",))
    st.title("Dashboard de Cumplimiento")
    st.caption("Fuente: data mart PostgreSQL (ETL desde SIRADMIN)")
    st.sidebar.header("Filtros")

    hoy = date.today()
    primer_dia_mes = hoy.replace(day=1)
    col_f1, col_f2 = st.sidebar.columns(2)
    with col_f1:
        fecha_inicio = st.date_input("Desde", value=primer_dia_mes, key="cum_f1")
    with col_f2:
        fecha_fin = st.date_input("Hasta", value=hoy, key="cum_f2")

    tipo_reporte = st.sidebar.selectbox(
        "Tipo de reporte", ["Reporte Operativo", "Reporte Administrativo"], key="cum_tr")
    tipo_operacion = st.sidebar.selectbox(
        "Tipo de operación", ["Todos", "Importación", "Exportación"], key="cum_to")
    cliente_filtro = st.sidebar.text_input("Cliente (contiene)", "", key="cum_cli")

    @st.cache_data(ttl=120)
    def cargar_cumplimiento(f_ini, f_fin):
        return query_pg(f"""
            SELECT * FROM cumplimiento_pedimentos
            WHERE pedimento_fecha_pago >= '{f_ini}' AND pedimento_fecha_pago <= '{f_fin}'
        """)

    df = cargar_cumplimiento(fecha_inicio, fecha_fin)
    if df.empty:
        st.warning("Sin datos para el rango seleccionado.")
        return

    df["patente_aduana"] = df.apply(
        lambda r: f"{r['patente']} | {r['aduana']}"
        if pd.notna(r["patente"]) and pd.notna(r["aduana"]) else "SIN PATENTE", axis=1)

    opciones_patente = ["TODAS"] + sorted(df["patente_aduana"].unique().tolist())
    patentes_sel = st.sidebar.multiselect("Patente / Aduana", opciones_patente, default=["TODAS"], key="cum_pat")

    if tipo_operacion == "Importación":
        df = df[df["tipo_operacion"] == "I"]
    elif tipo_operacion == "Exportación":
        df = df[df["tipo_operacion"] == "E"]
    if patentes_sel and "TODAS" not in patentes_sel:
        df = df[df["patente_aduana"].isin(patentes_sel)]
    if cliente_filtro.strip():
        df = df[df["cliente"].str.contains(cliente_filtro, case=False, na=False)]
    if df.empty:
        st.warning("Sin datos después de aplicar filtros.")
        return

    for col in ["fecha_revalidacion", "fecha_arribo", "fecha_pago",
                 "pedimento_fecha_pago", "fecha_cuenta_gastos", "fecha_contabilidad"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    df["transporte_real"] = df.apply(
        lambda r: clasificar_transporte(r["medio_transporte"], r["contenedores"], r["tipo_contenedor"]), axis=1)

    if tipo_reporte == "Reporte Operativo":
        df["param_fecha_inicio"] = df.apply(
            lambda r: obtener_fecha_mas_reciente(r["fecha_revalidacion"], r["fecha_arribo"]), axis=1)
        df["param_fecha_fin"] = df["fecha_pago"]
    else:
        df["param_fecha_inicio"] = df["fecha_contabilidad"]
        df["param_fecha_fin"] = df["fecha_cuenta_gastos"]

    df["dias_transcurridos"] = df.apply(
        lambda r: dias_habiles_oga(r["param_fecha_inicio"], r["param_fecha_fin"]), axis=1)
    df["meta_aplicada"] = df.apply(
        lambda r: meta_dinamica(
            {"Transporte_Real": r["transporte_real"], "Tipo Operación": r["tipo_operacion"]},
            tipo_reporte), axis=1)

    df = df.dropna(subset=["dias_transcurridos"])
    df["dias_transcurridos"] = df["dias_transcurridos"].astype(int)
    df["cumple"] = df.apply(
        lambda r: "SI CUMPLE" if r["dias_transcurridos"] <= r["meta_aplicada"] else "NO CUMPLE", axis=1)

    total = len(df)
    cumplidos = len(df[df["cumple"] == "SI CUMPLE"])
    pct = round(cumplidos * 100 / total, 1) if total > 0 else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Total pedimentos", f"{total:,}")
    c2.metric("Cumplidos", f"{cumplidos:,}")
    c3.metric("% Cumplimiento", f"{pct}%")

    st.subheader(f"Detalle — {tipo_reporte}")
    df_display = df[["pedimento", "pedimento_fecha_pago", "aduana", "tipo_operacion",
                      "cliente", "transporte_real", "dias_transcurridos", "meta_aplicada", "cumple"]].copy()
    df_display.columns = ["Pedimento", "Fecha Pago", "Aduana", "Tipo Op",
                           "Cliente", "Transporte", "Días", "Meta", "Cumplimiento"]
    df_display = df_display.sort_values("Fecha Pago", ascending=False)

    def color_cumple(val):
        if val == "SI CUMPLE":
            return "background-color: #d4edda; color: #155724"
        return "background-color: #f8d7da; color: #721c24"

    st.dataframe(df_display.style.map(color_cumple, subset=["Cumplimiento"]),
                 use_container_width=True, height=600)
    st.caption(f"Mostrando {len(df_display):,} pedimentos | Rango: {fecha_inicio} → {fecha_fin} | Reporte: {tipo_reporte}")


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

    ETAPAS = ["EN TRAFICO", "ADMINISTRATIVO", "CIERRE"]
    etapas_sel = st.sidebar.multiselect("Etapa de operación", ETAPAS, default=ETAPAS, key="scv1_etapa")

    solo_proforma = st.sidebar.checkbox("Solo referencias con proforma", value=False, key="scv1_prof")

    # ── WHERE dinámico ──
    conds = []
    if sucursales_sel and "TODAS" not in sucursales_sel:
        s = ", ".join([f"'{x}'" for x in sucursales_sel])
        conds.append(f"sucursal IN ({s})")
    if etapas_sel and len(etapas_sel) < len(ETAPAS):
        s = ", ".join([f"'{x}'" for x in etapas_sel])
        conds.append(f"etapa_operacion IN ({s})")
    if solo_proforma:
        conds.append("folio_proforma IS NOT NULL")
    where = ("WHERE " + " AND ".join(conds)) if conds else ""

    filtros_desc = (
        ("Suc: " + ", ".join(sucursales_sel) if "TODAS" not in sucursales_sel else "Todas sucursales")
        + " | " + ", ".join(etapas_sel)
        + (" | Con proforma" if solo_proforma else "")
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

    st.title("Score Card — Seguimiento Operativo")
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

    # ── Tabla de detalle (usa MV para velocidad — solo activos) ──
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
            FROM mv_scorecard_v1_activo
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

    if df.empty:
        st.warning("Sin datos para los filtros seleccionados.")
        return

    st.subheader(f"Detalle — {len(df):,} referencias")

    ESTILO_ETAPA = {
        "EN TRAFICO":     "background-color:#0d1f35;color:#4A90E2",
        "ADMINISTRATIVO": "background-color:#2e1d00;color:#E8A838",
        "CIERRE":         "background-color:#061a0f;color:#27AE60",
        "OTRO":           "background-color:#1a1a1a;color:#7F8C8D",
    }

    def _cel_etapa(val):
        return ESTILO_ETAPA.get(val, "")

    def color_trf(val):
        if not isinstance(val, (int, float)) or val == 0:
            return ""
        if val <= 3:   return "background-color: #1a4a1a; color: #4ADE80"
        if val <= 7:   return "background-color: #4a3800; color: #FCD34D"
        return "background-color: #4a1515; color: #F87171"

    def color_adm(val):
        if not isinstance(val, (int, float)) or val == 0:
            return ""
        if val <= 3:   return "background-color: #1a4a1a; color: #4ADE80"
        if val <= 7:   return "background-color: #4a3800; color: #FCD34D"
        return "background-color: #4a1515; color: #F87171"

    def color_cga(val):
        if not isinstance(val, (int, float)) or val == 0:
            return ""
        if val <= 5:   return "background-color: #1a4a1a; color: #4ADE80"
        return "background-color: #4a1515; color: #F87171"

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

    # CORRECCIÓN 2 — Paginación
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
        "Leyenda días — TRF/ADM: verde ≤3d · naranja ≤7d · rojo >7d | "
        "CGA: verde ≤5d · rojo >5d"
    )

    # ── Exportaciones ──
    st.divider()
    ex1, ex2 = st.columns(2)

    with ex1:
        buf_xl = io.BytesIO()
        df_show.to_excel(buf_xl, index=False, engine="openpyxl")
        buf_xl.seek(0)
        st.download_button(
            label="📥 Descargar Excel",
            data=buf_xl,
            file_name=f"scorecard_v1_{date.today().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    with ex2:
        # PDF: siempre las 3 etapas activas; respeta filtro de sucursal/proforma
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
        st.download_button(
            label="📄 Descargar PDF",
            data=pdf_bytes,
            file_name=f"scorecard_v1_{date.today().strftime('%Y%m%d')}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )


# ══════════════════════════════════════════════════════════════════════
# ROUTER
# ══════════════════════════════════════════════════════════════════════
vista = st.session_state.vista
if vista == "cumplimiento":
    vista_cumplimiento()
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
