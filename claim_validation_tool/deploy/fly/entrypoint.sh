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
exec "$@"
