#!/bin/bash
# Arranca el entorno de DESARROLLO en puerto 8503
# Uso: bash start-dev.sh

cd /var/www/html/ocmx/reporteador-maestro/

pkill -f "streamlit.*8503" 2>/dev/null
sleep 1

nohup .venv/bin/streamlit run src/canales/streamlit/app.py \
  --server.address=0.0.0.0 \
  --server.port=8503 \
  --server.baseUrlPath=reportes-dev \
  > logs/streamlit-dev.log 2>&1 &

sleep 3
ss -tlnp | grep 8503 && echo "DEV corriendo en http://192.168.5.232:8503/reportes-dev"
