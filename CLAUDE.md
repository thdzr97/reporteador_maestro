# CLAUDE.md — Reporteador Maestro
# Actualizado 25/06/2026 — Contexto completo para Claude Code (SSH al .232)

## ¿Qué es este proyecto?

Plataforma de reportes e inteligencia conversacional para datos de cumplimiento
aduanal del SIR de Ocampo Grupo Aduanal.
Líder técnico: Ing. Tona Hernández — Área de Nuevas Tecnologías.
Repo GitHub: https://github.com/<tu-usuario>/reporteador_maestro (rama main protegida)

---

## Servidor (innovation — 192.168.5.232)

- OS: Debian 12, usuario: ntadmin (sudo con password)
- Python: 3.13.5 | PostgreSQL: 17.6 en 127.0.0.1:5432
- Ruta del proyecto: /var/www/html/ocmx/reporteador-maestro/
- Venv: .venv | Puerto: 8503 | Logs: logs/
- Arrancar todo: bash scripts/start.sh
- Proyecto hermano (NO tocar): /var/www/html/ocmx/reporte-sir/ en puerto 8502

---

## Fuente de datos — SIRADMIN (SQL Server Windows)

- Host: 192.168.5.24:1433 | DB: SIRADMIN
- Driver: ODBC Driver 18 for SQL Server
- Parámetro crítico: Encrypt=no;TrustServerCertificate=yes;
- Credenciales: ver .env (nunca hardcodear)
- El puerto solo está abierto al host innovation — nunca a la red general

---

## Tablas y vistas clave de SIRADMIN

### Tabla central del sistema

**sir.SIR_60_REFERENCIAS** (213 cols) — tabla maestra, todo gira alrededor de ella
- FKs clave: nIdMtraSelAle67, nIdStatus73, nIdCliente, nIdEjecutivo
- Fechas críticas: dFechaApertura, dFechaDespacho, dEnvioContabilidad,
  dFechaCierreAdmin, dFechaCierreOper
- Calidad: nDiasObjCalidadDespacho, bObjCalidadCumplidoDespacho,
  nDiasObjCalidadCGA, bObjCalidadCumplidoCGA (campos BIT)
- NOTA: bObjCalidadCumplidoDespacho siempre False en 2026 — SIR no los llena
- NOTA: dEnvioContabilidad solo 21.8% tiene dato (referencias cerradas)

### Tablas relacionadas confirmadas

**sir.SIR_67_MTRA_SELEC_ALEATORIA** — selección aleatoria
- JOIN: r.nIdMtraSelAle67 = s.nIdMtraSelAle67
- Campos útiles: dFechaPrimSel, dFechaSegSel (fechas reales con dato)
- NOTA: bVerdePrimerSelec, bRojoPrimerSelec, bDesaduanado = siempre False — no usar

**sir.SIR_73_STATUS_REFERENCIAS** — catálogo de estatus (ID → descripción)

**Admin.vt_proformas_epg** — proformas/facturas CGA
- JOIN: p.Referencia = r.sReferencia
- Campos: Factura, UUIDCGA, descestatus (PAGADA/FACTURADA), Honorarios

**admin.ADMIN_VT_CGastosCabecera** — vista CGA completa (~160 cols)

**admin.ADMINO_15_CUENTAS_GASTOS** — detalle cuentas de gastos

### Vistas SIR ya exploradas (15 vistas, docs/diccionario_siradmin.md)

**Admin.SIR_VT_Sabana_Pedimento** — 212 cols, ratio 5.6x por fracciones/facturas
- IMPORTANTE: una referencia genera múltiples filas — siempre GROUP BY referencia
- Nombres exactos de columnas clave (verificados en código funcional):
  `[Referencia]`, `[Pedimento]`, `[Patente]`, `[Pedimento Fecha Pago]`,
  `[Cliente]`, `[Ejecutivo]`, `[Tipo Operación]` (con tilde),
  `[Nombre Aduana Despacho]`, `[Nombre Aduana Entrada]`,
  `[Primera Selección]` (con tilde), `[Segunda Selección]` (con tilde),
  `[Valor Aduana]`, `[Honorarios]`, `[TotalCGA]`,
  `[CantidadFacturas]`, `[CantidadPartidas]`,
  `[Referencia Fecha Apertura]`, `[Status/Observaciones]`,
  `[Clave Cliente]` (RFC), `[Régimen]` (con tilde),
  `[Clave Incoterm]`, `[Nombre País Vendedor/Comprador]` (con tilde),
  `[Nombre País Origen/Destino]` (con tilde), `[Fracciones]`,
  `[ObservacionesR]`, `[Pedimentos Pagados]`, `[Clave Pedimento]`
- Columnas NO confirmadas en la vista (pueden no existir):
  `[Sucursal]`, `[Promotor]`, `[Grupo]`, `[Pedimento Numero]`

**Admin.SIR_VT_Sabana_Pedimento_Admin** — variante administrativa

**Admin.SIR_VT_CuentaDeGastos** — 48,244 registros (más grande)

**Admin.SIR_VT_CCIngresosCobrados, SIR_VT_CCIngresosPendientes**

**Admin.SIR_VT_CCAntiguedadSaldoClientes**

**Admin.SIR_VT_OchentaVeinte** — análisis 80/20

### Pendiente (vista del analista para sc_v1 — 26/06/2026 10am)

El analista administrativo proporcionará la vista/tabla que usa para el Score
Card el 26/06/2026 a las 10am.

---

## Data mart PostgreSQL (reporteador_maestro)

### cumplimiento_pedimentos
- ETL: etl_cumplimiento.py | UPSERT por pedimento (UNIQUE constraint)
- Fuente: SIR_VT_Sabana_Pedimento | 1,475 registros
- Lógica: dias_habiles_oga() + meta_dinamica() importadas de reporte-sir

### sabana_pedimentos
- ETL: etl_sabana.py | DELETE+reload | GROUP BY referencia (ratio 1.00)
- Fuente: SIR_VT_Sabana_Pedimento | 2,444 referencias únicas
- Estrategia de agregación: valor_aduana=MAX, honorarios=MAX, total_cga=SUM,
  cantidad_facturas=SUM, cantidad_partidas=SUM, fecha_pago=MAX,
  status_referencia=MAX, ejecutivo=MAX, cliente=MAX

### scorecard_referencias
- ETL: etl_scorecard.py | TRUNCATE+reload
- Fuente: SIR_60_REFERENCIAS + SIR_67 + sábana (OUTER APPLY) | 3,533 referencias
- Métricas reales: despachado=(dFechaDespacho IS NOT NULL),
  fecha_prim_sel=dFechaPrimSel, fecha_seg_sel=dFechaSegSel
- 307 despachadas (8.7%), 2,713 con primera selección (77%)

### scorecard_v1
- ETL: etl_scorecard_v1.py | DELETE+reload | PENDIENTE de validación
- Fuente: SIR_60_REFERENCIAS + SIR_67 + sábana + vt_proformas_epg
- 3 etapas: EN_TRAFICO, ADMINISTRATIVO, CIERRE
- Lógica días (verificada con PDF 25/06/2026):
  - dias_trf = hábiles(fecha_pago → fec_selec_ale) si fechas distintas, else 0
  - dias_adm = hábiles(fec_selec_ale → dEnvioContabilidad)
  - dias_cga = hábiles(dEnvioContabilidad → dFechaCierreAdmin)
  - Método: sin contar día inicio, sí día fin (L-V)
- PENDIENTE: vista del analista para completar lógica de DIAS ADM

### reportes_guardados
- Sistema de versionado de reportes por usuario
- Tabla creada 25/06/2026 | UI: src/canales/streamlit/mis_reportes.py
- Versiones: 1.0=original, 1.1=ajuste menor, 2.0=cambio mayor

---

## Lógica de cumplimiento (importada de reporte-sir)

NO replicar estas funciones — importarlas desde:

```python
sys.path.insert(0, '/var/www/html/ocmx/reporte-sir')
from utils.calculos import (
    dias_habiles_oga, obtener_fecha_mas_reciente,
    clasificar_transporte, meta_dinamica, obtener_mes_espanol
)
```

Metas por tipo de transporte (config.py de reporte-sir):
- AÉREO: Operativo=3d, Administrativo=3d
- TERRESTRE: Operativo=3d, Administrativo=7d
- MARÍTIMO SUELTA: Operativo=10d, Expo=8d, Administrativo=3d
- MARÍTIMO CONTENEDOR: Operativo=10d, Expo=8d, Administrativo=10d

---

## Dashboard (Streamlit puerto 8503)

URL: http://192.168.5.232:8503/reporteador
Tema: .streamlit/config.toml (oscuro, Navy #1E2761, Ice #CADCFC)
Navegación: session_state (un solo app.py, sin pages/)

### Reportes activos (4):
1. Dashboard de Cumplimiento — lee cumplimiento_pedimentos
2. Sábana de Pedimentos — lee sabana_pedimentos
3. Score Card — lee scorecard_referencias
4. Mis Reportes — lee reportes_guardados

### Reportes próximos:
5. Score Card v1 — leerá scorecard_v1 (pendiente validación)

---

## Sistema de reportes guardados

Tabla PostgreSQL:

```sql
CREATE TABLE reportes_guardados (
    id            SERIAL PRIMARY KEY,
    nombre        VARCHAR(100) NOT NULL,
    version       VARCHAR(10)  NOT NULL DEFAULT '1.0',
    reporte_padre VARCHAR(50)  NOT NULL,
    columnas      JSONB,
    filtros       JSONB,
    creado_por    VARCHAR(100),
    creado_en     TIMESTAMP    DEFAULT NOW(),
    descripcion   TEXT,
    es_publico    BOOLEAN      DEFAULT FALSE,
    UNIQUE(nombre, version)
);
```

El código del reporte vive en GitHub con su tag de versión correspondiente.

---

## ETL automático

Script principal: scripts/run_etl.py (loop cada 90 seg)
ETLs en el loop:
1. etl_incremental() — cumplimiento_pedimentos (últimos 7 días, UPSERT)
2. run_etl_sabana(dias_atras=2) — sabana_pedimentos
3. run_etl_scorecard() — scorecard_referencias
4. run_etl_scorecard_v1() — pendiente de agregar cuando esté validado

---

## Arquitectura — reglas que NO se cambian

1. La IA NUNCA toca SIRADMIN — solo el ETL accede a SQL Server
2. ETL incremental cada 90 seg — no consulta directa en cada request
3. Monolito modular — no microservicios (equipo pequeño)
4. Sin GPU en el servidor — Hermes en CPU como fallback
5. Web primero — Telegram después (firewall bloqueó Telegram en ZorIA)
6. Router determinista — basado en catálogo, no heurística
7. Campos sensibles (RFC, razón social) marcados en semantic layer

---

## Git y versionado

Flujo:
- main: rama estable, siempre desplegable
- feature/*: nuevas funcionalidades
- fix/*: correcciones
- PR obligatorio antes de mergear a main
- Tag de versión en cada release: v0.1, v0.2, v1.0

Versión actual: v0.2 (4 reportes activos, ETL funcionando)

Comandos frecuentes desde el servidor:
```bash
cd /var/www/html/ocmx/reporteador-maestro
git status
git add -A
git commit -m "tipo: descripción corta"
git push origin feature/nombre-rama
```

---

## Lo que NO hacer

- NO tocar /var/www/html/ocmx/reporte-sir/ — en producción
- NO hardcodear credenciales — siempre .env con chmod 600
- NO usar OpenClaw para este proyecto
- NO implementar Telegram sin probar conectividad primero
- NO ejecutar sudo sin avisar a Tona (requiere password manual)
- NO hacer GROUP BY sin DISTINCT en sábana — duplica filas
- NO usar bObjCalidadCumplidoDespacho ni bRojoPrimerSelec — siempre False
- NO usar `pkill -f "streamlit run"` sin patrón específico — mata reporte-sir
  Usar: kill $(pgrep -f "streamlit run.*reporteador") 2>/dev/null || true
