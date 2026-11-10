#!/bin/sh
# First boot only: copy the seed organisations and accounts onto the empty volume.
# Later deploys leave /data alone, so accounts, claims and the audit log survive.
set -e
if [ ! -f /data/orgs/organisations.json ]; then
  echo "Seeding /data from the image"
  mkdir -p /data/logs
  cp -a /seed/orgs /data/orgs
  cp /seed/users.json /data/users.json
  chmod 600 /data/users.json
fi
# The demo's seed organisations are synthetic: mark them so (older volumes predate the mark)
for org in meridian lakeside; do
  python -m app.orgs sample-data "$org" on >/dev/null 2>&1 || true
done
exec "$@"
