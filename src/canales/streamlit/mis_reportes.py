"""
mis_reportes.py — Sistema de reportes guardados
Permite ver, crear y versionar reportes personalizados (como Power BI)
"""
import streamlit as st
import json
from sqlalchemy import text
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from src.etl.conexion import get_pg_engine, query_pg


def ir_a(v):
    st.session_state.vista = v


def siguiente_version(nombre, reporte_padre):
    """Calcula la siguiente versión para un reporte dado."""
    df = query_pg(f"""
        SELECT version FROM reportes_guardados
        WHERE nombre = '{nombre}' AND reporte_padre = '{reporte_padre}'
        ORDER BY creado_en DESC LIMIT 1
    """)
    if df.empty:
        return "1.0"
    ultima = df.iloc[0]["version"]
    partes = ultima.split(".")
    return f"{partes[0]}.{int(partes[1]) + 1}"


def guardar_reporte(nombre, version, padre, columnas, filtros, usuario, desc, publico):
    """Guarda un nuevo reporte o nueva versión en PostgreSQL."""
    engine = get_pg_engine()
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO reportes_guardados
                (nombre, version, reporte_padre, columnas, filtros, creado_por, descripcion, es_publico)
            VALUES
                (:nombre, :version, :padre, :columnas::jsonb, :filtros::jsonb, :usuario, :desc, :publico)
            ON CONFLICT (nombre, version) DO UPDATE
                SET columnas    = EXCLUDED.columnas,
                    filtros     = EXCLUDED.filtros,
                    descripcion = EXCLUDED.descripcion,
                    es_publico  = EXCLUDED.es_publico
        """), {
            "nombre": nombre, "version": version, "padre": padre,
            "columnas": json.dumps(columnas), "filtros": json.dumps(filtros),
            "usuario": usuario, "desc": desc, "publico": publico,
        })


def render_mis_reportes():
    """Pantalla principal de reportes guardados."""
    st.sidebar.button("← Volver al menú", on_click=ir_a, args=("inicio",))
    st.markdown("## Mis Reportes Guardados")
    st.markdown("Reportes personalizados — crea, versiona y comparte vistas de los datos.")
    st.divider()

    df = query_pg("""
        SELECT id, nombre, version, reporte_padre, creado_por,
               creado_en, descripcion, es_publico
        FROM reportes_guardados
        ORDER BY reporte_padre, nombre, version DESC
    """)

    if df.empty:
        st.info("No hay reportes guardados aún. Crea el primero desde cualquier reporte.")
        return

    padres = df["reporte_padre"].unique()

    for padre in padres:
        df_padre = df[df["reporte_padre"] == padre]
        with st.expander(f"📊 {padre.upper()} ({len(df_padre)} reportes)", expanded=True):
            for _, row in df_padre.iterrows():
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                with col1:
                    publico_icon = "🌐" if row["es_publico"] else "🔒"
                    st.markdown(f"**{publico_icon} {row['nombre']}**")
                    if row["descripcion"]:
                        st.caption(row["descripcion"])
                with col2:
                    st.markdown(f"**v{row['version']}**")
                    st.caption(str(row["creado_en"])[:10])
                with col3:
                    st.caption(row["creado_por"])
                with col4:
                    if st.button("Abrir", key=f"abrir_{row['id']}"):
                        st.session_state.vista = row["reporte_padre"]
                        st.session_state["reporte_guardado"] = row["id"]
                        st.rerun()

    st.divider()

    with st.expander("➕ Crear nuevo reporte o versión"):
        col1, col2 = st.columns(2)
        with col1:
            nombre = st.text_input("Nombre del reporte",
                                   placeholder="Ej: Score Card Aeropuertos")
            padre_sel = st.selectbox("Reporte base",
                                     ["scorecard_v1", "sabana", "cumplimiento", "scorecard"])
            usuario = st.text_input("Tu nombre", value="Tona Hernandez")
        with col2:
            desc = st.text_area("Descripción", height=100,
                                placeholder="¿Para qué sirve este reporte?")
            publico = st.checkbox("Visible para todos", value=False)

        st.caption("Las columnas y filtros se configuran desde el reporte base.")

        if st.button("💾 Guardar reporte", type="primary"):
            if not nombre:
                st.error("El nombre es obligatorio.")
            else:
                version = siguiente_version(nombre, padre_sel)
                guardar_reporte(
                    nombre=nombre, version=version, padre=padre_sel,
                    columnas=[], filtros={},
                    usuario=usuario, desc=desc, publico=publico,
                )
                st.success(f"✓ Reporte '{nombre}' guardado como v{version}")
                st.rerun()
