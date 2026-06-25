#!/bin/bash
# start.sh — Arranca Reporteador Maestro completo
# Uso: bash scripts/start.sh
cd /var/www/html/ocmx/reporteador-maestro

echo "── Reporteador Maestro ──────────────────────"

# ETL
pkill -f "run_etl.py" || true
sleep 1
nohup .venv/bin/python scripts/run_etl.py > logs/etl.log 2>&1 &
echo "✓ ETL arrancado (PID $!)"

# Streamlit
pkill -f "streamlit run.*reporteador-maestro" || true
sleep 1
nohup .venv/bin/streamlit run src/canales/streamlit/app.py \
  --server.address=0.0.0.0 \
  --server.port=8503 \
  --server.baseUrlPath=reporteador \
  > logs/streamlit.log 2>&1 &
echo "✓ Streamlit arrancado (PID $!)"

sleep 3
echo ""
echo "Estado:"
ps aux | grep -E "streamlit.*reporteador|run_etl" | grep -v grep
echo ""
echo "Dashboard: http://192.168.5.232:8503/reporteador"
echo "─────────────────────────────────────────────"
