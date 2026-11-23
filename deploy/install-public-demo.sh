#!/bin/bash
# Operación idempotente sobre una release revisada. No imprime credenciales.
set -euo pipefail
umask 077
public_host=${1:?Se requiere el hostname gratuito de la API}
[[ "$public_host" =~ ^nafta2go\.[0-9.]+\.sslip\.io$ ]] || exit 2
base=/opt/nafta2go
source_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
if ! docker compose version >/dev/null 2>&1; then
  install -d /usr/local/lib/docker/cli-plugins
  curl --fail --silent --show-error --location --retry 2 \
    https://github.com/docker/compose/releases/download/v2.39.2/docker-compose-linux-x86_64 \
    -o /usr/local/lib/docker/cli-plugins/docker-compose.next
  echo 'a55a8cd4ef103aac282812554e531aac8df7e914a287ee81e14d695556a22902  /usr/local/lib/docker/cli-plugins/docker-compose.next' | sha256sum -c -
  chmod 755 /usr/local/lib/docker/cli-plugins/docker-compose.next
  mv /usr/local/lib/docker/cli-plugins/docker-compose.next /usr/local/lib/docker/cli-plugins/docker-compose
fi
mkdir -p "$base/private/observability" "$base/proxy" "$base/observability"
sed -n 's/^NAFTA2GO_ADMIN_TOKEN=//p' "$base/private/runtime.env" > "$base/private/observability/api_admin_token"
aws ssm get-parameters --region us-east-2 --names /nafta2go/demo/grafana-admin \
  --with-decryption --query 'Parameters[0].Value' --output text > "$base/private/observability/grafana_admin_password"
[[ -s "$base/private/observability/api_admin_token" ]]
[[ -s "$base/private/observability/grafana_admin_password" ]]
chmod 444 "$base/private/observability/"*
cp -R "$source_dir/observability/." "$base/observability/"
cat > "$base/proxy/Caddyfile" <<EOF
$public_host {
  log {
    output discard
  }
  @metrics path /metrics
  respond @metrics 404
  redir /grafana /grafana/ 308
  handle /grafana/* {
    reverse_proxy 127.0.0.1:3000
  }
  handle {
    reverse_proxy 127.0.0.1:8000
  }
}
EOF
docker rm -f nafta2go-proxy 2>/dev/null || true
docker run -d --name nafta2go-proxy --restart unless-stopped --network host \
  -v "$base/proxy/Caddyfile:/etc/caddy/Caddyfile:ro" \
  -v nafta2go-caddy-data:/data -v nafta2go-caddy-config:/config caddy:2.10.2-alpine
export NAFTA2GO_PRIVATE_DIR="$base/private/observability" NAFTA2GO_PUBLIC_HOST="$public_host"
docker compose -p nafta2go-observability -f "$base/observability/aws-compose.yaml" up -d
for attempt in {1..30}; do
  if curl --fail --silent --max-time 5 --resolve "$public_host:443:127.0.0.1" "https://$public_host/health" >/dev/null; then
    echo 'Proxy HTTPS y observabilidad instalados'
    exit 0
  fi
  sleep 3
done
echo 'HTTPS aún no superó la verificación; conservar el acceso SSM' >&2
exit 3
