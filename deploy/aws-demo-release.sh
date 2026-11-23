#!/bin/bash
# Ejecutar como root mediante SSM. Sin secretos en argumentos ni salida.
set -euo pipefail
umask 077
smoke_source=${smoke_source:-$(cat "$(dirname "${BASH_SOURCE[0]}")/smoke.py")}

release_commit=${1:?Se requiere el commit revisado}
runtime_parameter=${2:?Se requiere el nombre del parámetro SecureString}
image=${3:?Se requiere la imagen de GHCR por digest}
mode=${4:-deploy}
[[ "$mode" == deploy || "$mode" == rollback ]] || exit 2
[[ "$release_commit" =~ ^[0-9a-f]{40}$ ]] || exit 2
[[ "$runtime_parameter" =~ ^/nafta2go/demo/[a-zA-Z0-9/_-]+$ ]] || exit 2
[[ "$image" =~ ^ghcr.io/estanislaomolina/nafta2go@sha256:[0-9a-f]{64}$ ]] || exit 2


base=${NAFTA2GO_DEPLOY_BASE:-/opt/nafta2go}
mkdir -p "$base/releases" "$base/private" "$base/data" "$base/backups"
chmod 700 "$base/private" "$base/backups"
exec 9>"$base/private/deployment.lock"
flock -n 9 || { echo "Ya existe un despliegue en curso" >&2; exit 7; }
if [[ "$mode" == rollback ]]; then
  [[ -f "$base/releases/$release_commit.image" ]] || exit 8
  [[ "$(cat "$base/releases/$release_commit.image")" == "$image" ]] || exit 8
fi
# El registro debe ser público: no se pasan credenciales de GHCR al host.
# Rechazar una imagen que no corresponde al commit revisado antes de migrar.
docker pull "$image"
[[ "$(docker image inspect "$image" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}')" == "$release_commit" ]] || exit 5
aws ssm get-parameters --region us-east-2 --names "$runtime_parameter" \
  --with-decryption --query 'Parameters[0].Value' --output text > "$base/private/runtime.env.next"
[[ -s "$base/private/runtime.env.next" ]] || exit 3
grep -q '^NAFTA2GO_API_TOKEN=.' "$base/private/runtime.env.next"
grep -q '^NAFTA2GO_ADMIN_TOKEN=.' "$base/private/runtime.env.next"
grep -q '^ORS_API_KEY=.' "$base/private/runtime.env.next"
mv "$base/private/runtime.env.next" "$base/private/runtime.env"

chown 10001:10001 "$base/data"

# El respaldo usa la API SQLite, también si existe un escritor concurrente.
if [[ -f "$base/data/nafta2go.db" ]]; then
  backup_name="$(date -u +%Y%m%dT%H%M%SZ).db"
  docker run --rm --user 0 -v "$base/data:/data" -v "$base/backups:/backups" \
    "$image" python -c 'import sqlite3,sys; src=sqlite3.connect("/data/nafta2go.db"); dst=sqlite3.connect("/backups/"+sys.argv[1]); src.backup(dst); assert dst.execute("pragma integrity_check").fetchone()[0]=="ok"' "$backup_name"
fi
# Las releases iniciales comparten esquema 0003; una migración futura necesita
# revisión explícita de compatibilidad antes de usar este rollback de código.
if [[ "$mode" == deploy ]]; then
  docker run --rm --env-file "$base/private/runtime.env" -v "$base/data:/app/data" "$image" alembic upgrade head
fi
# Adquirir datos es una operación independiente; readiness informa su disponibilidad.

old_image=$(cat "$base/current-image" 2>/dev/null || true)
start_api() {
  docker run -d --name nafta2go-api --restart unless-stopped \
    --env-file "$base/private/runtime.env" -v "$base/data:/app/data" \
    -p 127.0.0.1:8000:8000 "$1" uvicorn nafta2go.presentation.http:app \
    --host 0.0.0.0 --port 8000 --no-access-log --log-config deploy/logging.json
}
smoke() {
  for attempt in {1..30}; do
    if curl --fail --silent --max-time 2 http://127.0.0.1:8000/ready >/dev/null; then
      docker exec -i nafta2go-api python - <<< "$smoke_source"
      return $?
    fi
    sleep 2
  done
  return 1
}
# Se conserva el servicio anterior mientras se descarga y prepara la versión.
docker rm -f nafta2go-api 2>/dev/null || true
if ! start_api "$image" || ! smoke; then
  docker rm -f nafta2go-api 2>/dev/null || true
  if [[ -n "$old_image" ]] && start_api "$old_image" && smoke; then
    echo "Candidata $image falló en activación/smoke; restaurada $old_image" >&2
    exit 4
  fi
  echo "Candidata $image falló; recuperación de ${old_image:-ninguna} fallida" >&2
  exit 6
fi
printf '%s\n' "$image" > "$base/current-image"
printf '%s\n' "$image" > "$base/releases/$release_commit.image"
echo "Release instalada: $image; smoke aprobado"
docker image inspect "$image" --format '{{.Id}}'
