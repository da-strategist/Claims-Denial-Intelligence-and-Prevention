#!/bin/sh
# Serve the app at https://localhost:8443 (the API and `npm run dev` must be running).
# One-time setup, which asks for your Mac password: `mkcert -install`
set -e
cd "$(dirname "$0")"
if [ ! -f certs/localhost.pem ]; then
  mkdir -p -m 700 certs
  mkcert -cert-file certs/localhost.pem -key-file certs/localhost-key.pem localhost 127.0.0.1 ::1
  chmod 600 certs/localhost-key.pem
fi
exec caddy run --config Caddyfile.local --adapter caddyfile
