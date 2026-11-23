#!/bin/bash
# Instalar desde una release revisada que incluya este procedimiento.
set -euo pipefail
umask 077
[[ "$EUID" == 0 ]] || { echo 'Ejecutar como root' >&2; exit 2; }
bucket=${1:?Se requiere el bucket privado}
[[ "$bucket" =~ ^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$ ]] || exit 2
base=/opt/nafta2go
source_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
image=$(cat "$base/current-image")
docker run --rm "$image" python -m nafta2go.normalization --help | grep -q -- '--receipt'
# No cambiar ejecutables mientras un servicio los está usando.
for unit in nafta2go-aws-ingestion.service nafta2go-aws-monitor.service; do
  if systemctl is-active --quiet "$unit"; then
    echo 'Hay una ingesta o monitor activos; reintentar al finalizar' >&2
    exit 3
  fi
done
install -d -m 700 /etc/nafta2go "$base/ingestion"
printf 'NAFTA2GO_CAPTURE_BUCKET=%s\n' "$bucket" > /etc/nafta2go/ingestion-relay.env
for name in aws-ingestion-relay.sh aws-ingestion-monitor.sh; do
  install -m 700 "$source_dir/$name" "$base/ingestion/$name"
done
for name in nafta2go-aws-ingestion nafta2go-aws-monitor; do
  install -m 644 "$source_dir/$name.service" "$source_dir/$name.timer" /etc/systemd/system/
done
systemctl daemon-reload
systemctl enable --now nafta2go-aws-ingestion.timer nafta2go-aws-monitor.timer
systemctl list-timers 'nafta2go-aws-*' --no-pager
