#!/usr/bin/env bash
# Build the pilot bundle on your own computer:
#   claim_validation_tool/deploy/aws/bundle.sh
# Writes dist/vericlaim-pilot-<version>.tgz: the API (no tests), the built app, the shared
# code sets, and these setup scripts. No organisations, accounts or claims are in it.
# Upload it to CloudShell, then run aws/provision.sh (once) and aws/deploy.sh.
set -euo pipefail

repo=$(cd "$(dirname "$0")/../../.." && pwd)
tool="$repo/claim_validation_tool"
version="$(git -C "$repo" rev-parse --short HEAD)$(git -C "$repo" diff --quiet HEAD -- claim_validation_tool pyproject.toml uv.lock || echo -dirty)"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
stage="$work/vericlaim-pilot"
app="$stage/app"
mkdir -p "$app/claim_validation_tool/backend" "$app/claim_validation_tool/frontend"

echo "== API"
cp "$repo/pyproject.toml" "$repo/uv.lock" "$repo/.python-version" "$app/"
touch "$app/README.md"   # pyproject.toml names it
rsync -a --exclude tests --exclude evals --exclude __pycache__ --exclude '*.pyc' \
  "$tool/backend/app" "$app/claim_validation_tool/backend/"

echo "== App (npm ci && npm run build)"
build="$work/frontend"
rsync -a --exclude node_modules --exclude dist "$tool/frontend/" "$build/"
# No pilot contact address: the website isn't served by the pilot server
(cd "$build" && unset VITE_PILOT_CONTACT_EMAIL && npm ci --silent && VITE_API_BASE=/api npm run build --silent)
cp -R "$build/dist" "$app/claim_validation_tool/frontend/dist"

echo "== Shared code sets"
(cd "$tool/backend" && uv run --quiet python -m app.orgs code-sets "$app/code_sets")

echo "== Setup scripts"
mkdir -p "$stage/aws/server"
cp "$tool/deploy/aws/provision.sh" "$tool/deploy/aws/deploy.sh" "$tool/deploy/aws/config.env.example" \
  "$tool/deploy/aws/README.md" "$stage/aws/"
cp "$tool/deploy/aws/server/"* "$stage/aws/server/"
cp "$tool/deploy/security-headers.caddy" "$stage/aws/server/"
chmod +x "$stage/aws/"*.sh "$stage/aws/server/"*.sh "$stage/aws/server/vericlaim-admin"
echo "$version" > "$stage/VERSION"

# Nothing private goes in: no .env files, keys, or organisation data
if find "$stage" \( -name '.env*' -o -name '*.pem' -o -name '*.key' -o -name 'users.json' -o -name 'orgs' \) | grep -q .; then
  echo "Refusing: the bundle would contain a secret or data file" >&2
  find "$stage" \( -name '.env*' -o -name '*.pem' -o -name '*.key' -o -name 'users.json' -o -name 'orgs' \) >&2
  exit 1
fi

mkdir -p "$repo/dist"
out="$repo/dist/vericlaim-pilot-$version.tgz"
COPYFILE_DISABLE=1 tar czf "$out" -C "$work" vericlaim-pilot
echo "Built $out ($(du -h "$out" | cut -f1))"
