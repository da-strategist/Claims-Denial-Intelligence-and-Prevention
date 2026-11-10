#!/usr/bin/env bash
# Install or update the app on the pilot server. Run in AWS CloudShell after provision.sh:
#   ./aws/deploy.sh ~/vericlaim-pilot-<version>.tgz
# Uploads the bundle to the release bucket, then has the server fetch and install it
# (Systems Manager Run Command: no SSH). Prints the server's output.
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
# shellcheck disable=SC1091
. "$here/config.env"
STATE="$HOME/.$NAME.state"
[ -f "$STATE" ] || { echo "Run ./aws/provision.sh first" >&2; exit 1; }
# shellcheck disable=SC1090
. "$STATE"
BUNDLE=${1:?Give the bundle: ./aws/deploy.sh vericlaim-pilot-<version>.tgz}
[ -f "$BUNDLE" ] || { echo "No file $BUNDLE" >&2; exit 1; }
export AWS_REGION="$REGION" AWS_DEFAULT_REGION="$REGION" AWS_PAGER=""
DOMAIN=${DOMAIN:-${PUBLIC_IP//./-}.sslip.io}

KEY="releases/$(basename "$BUNDLE")"
echo "Uploading $(basename "$BUNDLE")"
aws s3 cp "$BUNDLE" "s3://$BUCKET/$KEY" --only-show-errors

echo "Waiting for the server to be reachable by Systems Manager"
for _ in $(seq 1 30); do
  status=$(aws ssm describe-instance-information --filters "Key=InstanceIds,Values=$INSTANCE_ID" \
    --query 'InstanceInformationList[0].PingStatus' --output text 2>/dev/null || true)
  [ "$status" = "Online" ] && break
  sleep 10
done
[ "$status" = "Online" ] || { echo "The server isn't online in Systems Manager yet; try again in a few minutes" >&2; exit 1; }

params=$(python3 - "$BUCKET" "$KEY" "$NAME" "$REGION" "$DOMAIN" "$KMS_KEY_ARN" <<'EOF'
import json, shlex, sys
bucket, key, name, region, domain, kms = sys.argv[1:]
env = " ".join(f"{k}={shlex.quote(v)}" for k, v in
               {"NAME": name, "REGION": region, "DOMAIN": domain, "KMS_KEY_ARN": kms}.items())
print(json.dumps({"commands": [
    "set -e",
    "rm -rf /tmp/vericlaim-install && mkdir -p /tmp/vericlaim-install",
    f"aws s3 cp s3://{bucket}/{key} /tmp/vericlaim-install/bundle.tgz --only-show-errors --region {region}",
    "tar xzf /tmp/vericlaim-install/bundle.tgz -C /tmp/vericlaim-install",
    f"env {env} bash /tmp/vericlaim-install/vericlaim-pilot/aws/server/install.sh",
], "executionTimeout": ["1800"]}))
EOF
)
COMMAND=$(aws ssm send-command --instance-ids "$INSTANCE_ID" --document-name AWS-RunShellScript \
  --comment "$NAME deploy $(basename "$BUNDLE")" --parameters "$params" --timeout-seconds 600 \
  --query Command.CommandId --output text)
echo "Installing (command $COMMAND); the first install takes a few minutes"
while :; do
  sleep 10
  state=$(aws ssm get-command-invocation --command-id "$COMMAND" --instance-id "$INSTANCE_ID" \
    --query Status --output text 2>/dev/null || echo Pending)
  case "$state" in Pending|InProgress|Delayed) printf . ;; *) echo; break ;; esac
done
aws ssm get-command-invocation --command-id "$COMMAND" --instance-id "$INSTANCE_ID" \
  --query '[StandardOutputContent, StandardErrorContent]' --output text | tail -40
[ "$state" = "Success" ] || { echo "Install finished with status $state" >&2; exit 1; }
echo "Live at https://$DOMAIN/app"
