#!/usr/bin/env bash
# Starts the API (systemd: vericlaim-api.service). Reads the Anthropic key, if one has been
# stored, from Parameter Store, so it is never written to disk on the server.
set -euo pipefail
key=$(aws ssm get-parameter --region "$AWS_REGION" --name "$PARAMETER_PREFIX/anthropic-api-key" \
  --with-decryption --query Parameter.Value --output text 2>/dev/null || true)
if [ -n "$key" ] && [ "$key" != "None" ]; then
  export ANTHROPIC_API_KEY="$key"
fi
cd /srv/vericlaim/current/claim_validation_tool/backend
exec /srv/vericlaim/current/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-server-header
