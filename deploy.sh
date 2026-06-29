#!/bin/bash
# Despliega la última versión de main a producción
# Uso: bash deploy.sh

cd /var/www/html/ocmx/reporteador-maestro-prod/

echo "=== Pull desde main ==="
git pull origin main

echo "=== Instalar dependencias nuevas si las hay ==="
.venv/bin/pip install --quiet -r requirements.txt

echo "=== Reiniciar servicio ==="
sudo systemctl restart reporteador-maestro.service
sleep 3
sudo systemctl status reporteador-maestro.service --no-pager | grep -E "Active|PID"
echo "=== Deploy completado ==="
