#!/usr/bin/env bash
# Runs on the pilot server (Amazon Linux 2023, arm64) as root, started by deploy.sh.
# Installs or updates: swap, security updates, uv + Python, Caddy, the app, and its services.
# Safe to run again: each deploy adds a release and switches to it; data is never touched.
#
# Layout:
#   /srv/vericlaim/releases/<version>   the app (read-only to the service)
#   /srv/vericlaim/current              -> the release in use
#   /srv/vericlaim/data                 organisations, accounts, audit logs (encrypted files)
#   /etc/vericlaim/api.env              the API's settings
set -euo pipefail

: "${NAME:?}" "${REGION:?}" "${DOMAIN:?}" "${KMS_KEY_ARN:?}"
bundle=$(cd "$(dirname "$0")/../.." && pwd)        # the unpacked bundle
version=$(cat "$bundle/VERSION")
base=/srv/vericlaim

UV_VERSION=0.8.12
UV_SHA256=9a8a53df515bd64d423c85ace7ddca08fb9a91d8a115934c4495b5cf74c60ea6
CADDY_VERSION=2.10.0
CADDY_SHA512=6d100bfd609e8cfe6a51afe1b86066ac68f53ac56670c74a7d7537d93c643aa7f0e82b9f3083218eee1d369a427bfcdafcb445c7a730f9fc0ddf546401d95484

step() { printf '\n== %s\n' "$*"; }

step "Swap (2 GB, so 1 GB of memory is enough)"
if ! swapon --show | grep -q /swapfile; then
  dd if=/dev/zero of=/swapfile bs=1M count=2048 status=none
  chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap defaults 0 0' >> /etc/fstab
fi
swapon --show

step "Security updates, applied automatically"
dnf -y -q install dnf-automatic >/dev/null
sed -i 's/^upgrade_type.*/upgrade_type = security/; s/^apply_updates.*/apply_updates = yes/' /etc/dnf/automatic.conf
systemctl enable --now dnf-automatic.timer >/dev/null

step "Accounts"
id vericlaim >/dev/null 2>&1 || useradd --system --home-dir "$base" --shell /sbin/nologin vericlaim
id caddy >/dev/null 2>&1 || useradd --system --home-dir /var/lib/caddy --shell /sbin/nologin caddy
install -d -m 755 "$base" "$base/releases"
install -d -m 700 -o vericlaim -g vericlaim "$base/data" "$base/data/logs"
install -d -m 750 -o root -g vericlaim /etc/vericlaim
install -d -m 700 -o caddy -g caddy /var/lib/caddy

step "uv $UV_VERSION"
if [ "$(/usr/local/bin/uv --version 2>/dev/null | cut -d' ' -f2)" != "$UV_VERSION" ]; then
  tmp=$(mktemp -d)
  curl -fsSL -o "$tmp/uv.tgz" "https://github.com/astral-sh/uv/releases/download/$UV_VERSION/uv-aarch64-unknown-linux-gnu.tar.gz"
  echo "$UV_SHA256  $tmp/uv.tgz" | sha256sum -c --quiet
  tar xzf "$tmp/uv.tgz" -C "$tmp"
  install -m 755 "$tmp"/uv-aarch64-unknown-linux-gnu/uv /usr/local/bin/uv
  rm -rf "$tmp"
fi

step "Caddy $CADDY_VERSION"
if [ "$(/usr/local/bin/caddy version 2>/dev/null | cut -d' ' -f1)" != "v$CADDY_VERSION" ]; then
  tmp=$(mktemp -d)
  curl -fsSL -o "$tmp/caddy.tgz" "https://github.com/caddyserver/caddy/releases/download/v$CADDY_VERSION/caddy_${CADDY_VERSION}_linux_arm64.tar.gz"
  echo "$CADDY_SHA512  $tmp/caddy.tgz" | sha512sum -c --quiet
  tar xzf "$tmp/caddy.tgz" -C "$tmp" caddy
  install -m 755 "$tmp/caddy" /usr/local/bin/caddy
  rm -rf "$tmp"
fi

step "App $version"
release="$base/releases/$version"
rm -rf "$release.new"
cp -a "$bundle/app" "$release.new"
export UV_PYTHON_INSTALL_DIR="$base/python" UV_CACHE_DIR=/var/cache/vericlaim-uv UV_NO_PROGRESS=1
(cd "$release.new" && uv sync --frozen --no-dev --no-install-project --quiet)
chown -R root:root "$release.new" && chmod -R go-w "$release.new"
chmod -R a+rX "$base/python"
rm -rf "$release" && mv "$release.new" "$release"
ln -sfn "$release" "$base/current"

step "Settings"
cat > /etc/vericlaim/api.env <<EOF
# Written by install.sh on each deploy. Secrets aren't here: the Anthropic key is read from
# Parameter Store (/$NAME/anthropic-api-key) when the API starts.
RCM_ENVIRONMENT=production
RCM_COOKIE_SECURE=1
RCM_ALLOWED_ORIGINS=https://$DOMAIN
RCM_PUBLIC_URL=https://$DOMAIN
RCM_KEY_PROVIDER=aws-kms
RCM_KMS_KEY_ID=$KMS_KEY_ARN
AWS_REGION=$REGION
RCM_ORGS_DIR=$base/data/orgs
RCM_USERS_FILE=$base/data/users.json
RCM_AUDIT_FILE=$base/data/logs/audit.jsonl
RCM_CODE_SETS_DIR=$base/current/code_sets
PARAMETER_PREFIX=/$NAME
EOF
chmod 640 /etc/vericlaim/api.env && chown root:vericlaim /etc/vericlaim/api.env
cat > /etc/vericlaim/caddy.env <<EOF
RCM_DOMAIN=$DOMAIN
RCM_FRONTEND_DIST=$base/current/claim_validation_tool/frontend/dist
EOF
install -d -m 755 /etc/caddy
install -m 644 "$bundle/aws/server/Caddyfile" /etc/caddy/Caddyfile
install -m 644 "$bundle/aws/server/security-headers.caddy" /etc/caddy/security-headers.caddy
install -m 755 "$bundle/aws/server/start-api.sh" /usr/local/bin/vericlaim-start-api
install -m 755 "$bundle/aws/server/vericlaim-admin" /usr/local/bin/vericlaim-admin
install -m 644 "$bundle/aws/server/vericlaim-api.service" "$bundle/aws/server/caddy.service" /etc/systemd/system/
systemctl daemon-reload

step "Starting"
systemctl enable vericlaim-api caddy >/dev/null 2>&1
systemctl restart vericlaim-api
for _ in $(seq 1 60); do
  curl -fsS http://127.0.0.1:8000/api/health >/dev/null 2>&1 && break
  sleep 2
done
if ! curl -fsS http://127.0.0.1:8000/api/health; then
  echo "The API didn't start:" >&2
  journalctl -u vericlaim-api -n 40 --no-pager >&2
  exit 1
fi
echo
systemctl restart caddy
sleep 3
systemctl is-active caddy

# Keep the 3 newest releases
ls -1dt "$base"/releases/*/ | tail -n +4 | xargs -r rm -rf
rm -rf /tmp/vericlaim-install
echo "Installed $version at https://$DOMAIN"
