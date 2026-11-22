#!/bin/bash
# Ejecutar como root. Sólo se recibe el nombre de SecureString, nunca el token.
set -euo pipefail
umask 077
mode=${1:-quick}
parameter=${2:-}
[[ "$mode" == quick || "$mode" == managed ]] || exit 2
if [[ "$mode" == managed ]]; then
  [[ "$parameter" =~ ^/nafta2go/demo/[a-zA-Z0-9/_-]+$ ]] || exit 2
fi
source_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
temporary=$(mktemp)
trap 'rm -f "$temporary"' EXIT
curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
  --connect-timeout 5 --max-time 90 --retry 2 \
  https://github.com/cloudflare/cloudflared/releases/download/2026.11.1/cloudflared-linux-amd64 \
  --output "$temporary"
printf '%s  %s\n' '97bb3b02d23a5980fc9c15a1a270e692da1923f103f920d5b16d4931d5ab55e7' "$temporary" | sha256sum --check --status
install -m 0755 "$temporary" /usr/local/bin/cloudflared
install -m 0644 "$source_dir/nafta2go-tunnel.service" /etc/systemd/system/nafta2go-tunnel.service
mkdir -p /etc/systemd/system/nafta2go-tunnel.service.d
if [[ "$mode" == managed ]]; then
  mkdir -p /etc/nafta2go
  chmod 700 /etc/nafta2go
  aws ssm get-parameters --region us-east-2 --names "$parameter" --with-decryption \
    --query 'Parameters[0].Value' --output text > /etc/nafta2go/cloudflare-token.next
  [[ -s /etc/nafta2go/cloudflare-token.next ]] || exit 3
  if grep -qx None /etc/nafta2go/cloudflare-token.next; then exit 3; fi
  chmod 600 /etc/nafta2go/cloudflare-token.next
  mv /etc/nafta2go/cloudflare-token.next /etc/nafta2go/cloudflare-token
  install -m 0644 "$source_dir/nafta2go-tunnel-managed.conf" /etc/systemd/system/nafta2go-tunnel.service.d/managed.conf
else
  rm -f /etc/systemd/system/nafta2go-tunnel.service.d/managed.conf
fi
systemctl daemon-reload
systemctl enable nafta2go-tunnel.service
systemctl restart nafta2go-tunnel.service
systemctl is-active --quiet nafta2go-tunnel.service
printf 'Servicio HTTPS instalado en modo %s; el apagado de demo no se modifica\n' "$mode"
