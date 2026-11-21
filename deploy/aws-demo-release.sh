#!/bin/bash
# Ejecutar como root mediante SSM. Sin secretos en argumentos ni salida.
set -euo pipefail
umask 077

release_commit=${1:?Se requiere el commit revisado}
runtime_parameter=${2:?Se requiere el nombre del parámetro SecureString}
capture_file=${3:-}
[[ "$release_commit" =~ ^[0-9a-f]{40}$ ]] || exit 2
[[ "$runtime_parameter" =~ ^/nafta2go/demo/[a-zA-Z0-9/_-]+$ ]] || exit 2
[[ -z "$capture_file" || "$capture_file" =~ ^/app/data/imports/[0-9a-f]{64}\.csv$ ]] || exit 2

base=${NAFTA2GO_DEPLOY_BASE:-/opt/nafta2go}
release_dir="$base/releases/$release_commit"
image="nafta2go:$release_commit"
mkdir -p "$release_dir" "$base/private" "$base/data" "$base/backups"
chmod 700 "$base/private" "$base/backups"
aws ssm get-parameters --region us-east-2 --names "$runtime_parameter" \
  --with-decryption --query 'Parameters[0].Value' --output text > "$base/private/runtime.env.next"
[[ -s "$base/private/runtime.env.next" ]] || exit 3
grep -q '^NAFTA2GO_API_TOKEN=.' "$base/private/runtime.env.next"
grep -q '^NAFTA2GO_ADMIN_TOKEN=.' "$base/private/runtime.env.next"
grep -q '^ORS_API_KEY=.' "$base/private/runtime.env.next"
mv "$base/private/runtime.env.next" "$base/private/runtime.env"

if [[ ! -f "$release_dir/Dockerfile" ]]; then
  curl --fail --silent --show-error --location --retry 2 \
    "https://github.com/estanislaomolina/nafta2go/archive/$release_commit.tar.gz" \
    --output "$base/private/source.tar.gz"
  tar -xzf "$base/private/source.tar.gz" --strip-components=1 -C "$release_dir"
fi
docker build --label "org.opencontainers.image.revision=$release_commit" -t "$image" "$release_dir"
chown 10001:10001 "$base/data"

# El respaldo usa la API SQLite, también si existe un escritor concurrente.
if [[ -f "$base/data/nafta2go.db" ]]; then
  backup_name="$(date -u +%Y%m%dT%H%M%SZ).db"
  docker run --rm --user 0 -v "$base/data:/data" -v "$base/backups:/backups" \
    "$image" python -c 'import sqlite3,sys; src=sqlite3.connect("/data/nafta2go.db"); dst=sqlite3.connect("/backups/"+sys.argv[1]); src.backup(dst); assert dst.execute("pragma integrity_check").fetchone()[0]=="ok"' "$backup_name"
fi
# Las releases iniciales comparten esquema 0003; una migración futura necesita
# revisión explícita de compatibilidad antes de usar este rollback de código.
docker run --rm --env-file "$base/private/runtime.env" -v "$base/data:/app/data" "$image" alembic upgrade head
ingest=(python -m nafta2go.normalization --source vigente --json)
if [[ -n "$capture_file" ]]; then ingest+=(--file "$capture_file"); fi
docker run --rm --env-file "$base/private/runtime.env" -v "$base/data:/app/data" "$image" "${ingest[@]}"

old_image=$(cat "$base/current-image" 2>/dev/null || true)
start_api() {
  docker run -d --name nafta2go-api --restart unless-stopped \
    --env-file "$base/private/runtime.env" -v "$base/data:/app/data" \
    -p 127.0.0.1:8000:8000 "$1" uvicorn nafta2go.presentation.http:app \
    --host 0.0.0.0 --port 8000 --no-access-log --log-config deploy/logging.json
}
ready() {
  for attempt in {1..30}; do
    if curl --fail --silent --max-time 2 http://127.0.0.1:8000/ready >/dev/null; then return 0; fi
    sleep 2
  done
  return 1
}
# Se conserva el servicio anterior mientras se construye y prepara la versión.
docker rm -f nafta2go-api 2>/dev/null || true
if ! start_api "$image" || ! ready; then
  docker rm -f nafta2go-api 2>/dev/null || true
  if [[ -n "$old_image" ]]; then start_api "$old_image"; ready; fi
  echo 'La release candidata falló; se intentó recuperar la imagen anterior' >&2
  exit 4
fi
printf '%s\n' "$image" > "$base/current-image"
echo 'Release instalada y readiness correcto'
docker image inspect "$image" --format '{{.Id}}'
