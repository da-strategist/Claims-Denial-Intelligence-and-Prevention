#!/bin/sh
# Stage a minimal build context and deploy the API to Fly.io.
# Only the API code, the synthetic data and a seed of orgs/ + users.json go into the image.
set -e
here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/../../.." && pwd)            # Healthcare_RCM_Project/
backend="$repo/claim_validation_tool/backend"
ctx=$(mktemp -d)
trap 'rm -rf "$ctx"' EXIT

mkdir -p "$ctx/Data" "$ctx/claim_validation_tool/backend" "$ctx/seed"
cp "$repo/pyproject.toml" "$repo/uv.lock" "$ctx/"
cp -R "$repo/Data/raw_data" "$ctx/Data/raw_data"
rsync -a --exclude tests --exclude __pycache__ "$backend/app" "$ctx/claim_validation_tool/backend/"
rsync -a --exclude logs "$backend/orgs" "$ctx/seed/"
cp "$backend/users.json" "$ctx/seed/users.json"
cp "$here/Dockerfile" "$here/entrypoint.sh" "$here/fly.toml" "$ctx/"
chmod +x "$ctx/entrypoint.sh"

# Meridian's data path is relative to the local repo; point it at the image's copy
python3 - "$ctx/seed/orgs/organisations.json" <<'EOF'
import json, sys
path = sys.argv[1]
registry = json.load(open(path))
for org in registry["organisations"]:
    if org["data_dir"].endswith("Data/raw_data"):
        org["data_dir"] = "/app/Data/raw_data"
json.dump(registry, open(path, "w"), indent=2)
EOF

cd "$ctx"
if [ "$1" = "--local" ]; then
  docker build -t claustrarcm-demo-api .   # build only, to try it with docker run
else
  fly deploy --config fly.toml "$@"
fi
