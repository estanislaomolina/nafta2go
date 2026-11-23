#!/bin/bash
set -euo pipefail
base=${NAFTA2GO_DEPLOY_BASE:-/opt/nafta2go}
image=$(cat "$base/current-image")
exec docker run --rm --env-file "$base/private/runtime.env" \
  -v "$base/data:/app/data" "$image" python -m nafta2go.monitor
