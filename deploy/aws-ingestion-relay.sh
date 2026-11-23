#!/bin/bash
# Ejecutar como root desde systemd. AWS CLI usa el rol de la instancia (IMDSv2).
set -euo pipefail
umask 077
export AWS_RETRY_MODE=standard AWS_MAX_ATTEMPTS=3
base=${NAFTA2GO_DEPLOY_BASE:-/opt/nafta2go}
bucket=${NAFTA2GO_CAPTURE_BUCKET:?Falta el bucket privado de capturas}
[[ "$bucket" =~ ^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$ ]] || exit 2
exec 9>"$base/private/deployment.lock"
flock -w 60 9 || exit 3
image=$(cat "$base/current-image")
mkdir -p "$base/data/imports"
transfer_dir=$(mktemp -d "$base/data/imports/relay-XXXXXXXX")
completed=false
trap 'if [[ "$completed" != true ]]; then rm -rf -- "$transfer_dir"; fi' EXIT
aws s3api get-object --region us-east-2 --bucket "$bucket" \
  --key vigente/latest.json "$transfer_dir/receipt.json" >/dev/null
# La ruta de S3 se deriva sólo de un digest hexadecimal, nunca de una ruta recibida.
digest=$(python3 - "$transfer_dir/receipt.json" <<'PY'
import json, re, sys
from pathlib import Path
path = Path(sys.argv[1])
assert path.stat().st_size <= 16384, 'Recibo demasiado grande'
digest = json.loads(path.read_text())['sha256']
assert isinstance(digest, str) and re.fullmatch('[0-9a-f]{64}', digest), 'Digest inválido'
print(digest)
PY
)
aws s3api get-object --region us-east-2 --bucket "$bucket" \
  --key "vigente/$digest.csv" "$transfer_dir/capture.csv" >/dev/null
# El usuario de la imagen necesita atravesar imports y leer los originales.
chown 10001:10001 "$base/data/imports" "$transfer_dir" "$transfer_dir/"*
relative_dir="/app/data/imports/$(basename "$transfer_dir")"
# Conservar originales desde que pueden quedar referenciados en una transacción,
# incluso si el contenedor se interrumpe después del commit y antes de responder.
completed=true
docker run --rm --env-file "$base/private/runtime.env" \
  -v "$base/data:/app/data" "$image" \
  python -m nafta2go.normalization --source vigente --json \
  --file "$relative_dir/capture.csv" --receipt "$relative_dir/receipt.json"
