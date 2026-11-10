#!/usr/bin/env bash
# Create the AWS pilot server's resources, once. Run in AWS CloudShell (us-east-1), from the
# unpacked bundle:  ./aws/provision.sh
#
# Creates, each only if it isn't there yet (safe to run again):
#   KMS key + alias/<NAME>          the master key for encryption at rest   ~$1.00/month
#   S3 bucket <NAME>-deploy-<acct>  release bundles only (no patient data)  ~$0.00
#   IAM role + instance profile     what the server may do (nothing else)   free
#   Security group                  HTTPS (443) and HTTP (80, for the certificate); no SSH
#   Daily snapshots, kept 7 days    Data Lifecycle Manager                  ~$0.50/month
#   EC2 instance                    t4g.micro, encrypted 20 GB gp3 disk     ~$7.70/month
#   Elastic IP                      the server's fixed public address       ~$3.65/month
#   Monthly budget alert            emails at 50%/100% of BUDGET_USD        free
#
# Nothing here opens SSH: the server is reached with Session Manager (Systems Manager).
# Don't run this before the AWS Business Associate Addendum is accepted.
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
[ -f "$here/config.env" ] || { echo "Copy $here/config.env.example to config.env and fill it in" >&2; exit 1; }
# shellcheck disable=SC1091
. "$here/config.env"
: "${NAME:?}" "${REGION:?}" "${INSTANCE_TYPE:?}" "${DISK_GB:?}" "${BUDGET_USD:?}"
[ -n "${BUDGET_EMAIL:-}" ] || { echo "Set BUDGET_EMAIL in config.env" >&2; exit 1; }
export AWS_REGION="$REGION" AWS_DEFAULT_REGION="$REGION" AWS_PAGER=""

STATE="$HOME/.$NAME.state"   # IDs of what was created; deploy.sh reads it
touch "$STATE"
save() { grep -v "^$1=" "$STATE" > "$STATE.tmp" || true; echo "$1=$2" >> "$STATE.tmp"; mv "$STATE.tmp" "$STATE"; }
say() { printf '\n== %s\n' "$*"; }

ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
TAGS="Key=Project,Value=$NAME"
say "Account ${ACCOUNT:0:4}…, region $REGION"

# --- KMS key ----------------------------------------------------------------------------
say "KMS key"
KEY_ARN=$(aws kms describe-key --key-id "alias/$NAME" --query KeyMetadata.Arn --output text 2>/dev/null || true)
if [ -z "$KEY_ARN" ] || [ "$KEY_ARN" = "None" ]; then
  KEY_ARN=$(aws kms create-key --description "$NAME master key (wraps each organisation's data key)" \
    --tags TagKey=Project,TagValue="$NAME" --query KeyMetadata.Arn --output text)
  aws kms create-alias --alias-name "alias/$NAME" --target-key-id "$KEY_ARN"
  echo "created $KEY_ARN"
else
  echo "exists"
fi
aws kms enable-key-rotation --key-id "$KEY_ARN"
save KMS_KEY_ARN "$KEY_ARN"

# --- Release bucket ---------------------------------------------------------------------
say "Release bucket"
BUCKET="$NAME-deploy-$ACCOUNT"
if ! aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  if [ "$REGION" = "us-east-1" ]; then
    aws s3api create-bucket --bucket "$BUCKET" >/dev/null
  else
    aws s3api create-bucket --bucket "$BUCKET" --create-bucket-configuration LocationConstraint="$REGION" >/dev/null
  fi
  echo "created $BUCKET"
else
  echo "exists"
fi
aws s3api put-public-access-block --bucket "$BUCKET" --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-tagging --bucket "$BUCKET" --tagging "TagSet=[{Key=Project,Value=$NAME}]"
# Old bundles go after 30 days, so storage stays at nearly nothing
aws s3api put-bucket-lifecycle-configuration --bucket "$BUCKET" --lifecycle-configuration \
  '{"Rules":[{"ID":"expire-old-releases","Status":"Enabled","Filter":{"Prefix":"releases/"},"Expiration":{"Days":30}}]}'
save BUCKET "$BUCKET"

# --- IAM role for the server ------------------------------------------------------------
say "Server role"
ROLE="$NAME-server"
if ! aws iam get-role --role-name "$ROLE" >/dev/null 2>&1; then
  aws iam create-role --role-name "$ROLE" --tags "$TAGS" --assume-role-policy-document \
    '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}' >/dev/null
  echo "created $ROLE"
else
  echo "exists"
fi
# Session Manager (shell access without SSH) and Run Command (deploys)
aws iam attach-role-policy --role-name "$ROLE" --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
aws iam put-role-policy --role-name "$ROLE" --policy-name "$NAME-server" --policy-document "$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {"Sid": "MasterKey", "Effect": "Allow",
     "Action": ["kms:Encrypt", "kms:Decrypt", "kms:DescribeKey"], "Resource": "$KEY_ARN"},
    {"Sid": "Releases", "Effect": "Allow", "Action": "s3:GetObject", "Resource": "arn:aws:s3:::$BUCKET/releases/*"},
    {"Sid": "Secrets", "Effect": "Allow", "Action": ["ssm:GetParameter"],
     "Resource": "arn:aws:ssm:$REGION:$ACCOUNT:parameter/$NAME/*"}
  ]
}
EOF
)"
if ! aws iam get-instance-profile --instance-profile-name "$ROLE" >/dev/null 2>&1; then
  aws iam create-instance-profile --instance-profile-name "$ROLE" >/dev/null
  aws iam add-role-to-instance-profile --instance-profile-name "$ROLE" --role-name "$ROLE"
  echo "waiting for the new role to be usable"; sleep 15
fi

# --- Security group ---------------------------------------------------------------------
say "Security group"
VPC=$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text)
[ "$VPC" != "None" ] || { echo "No default VPC in $REGION: create one (VPC console → Actions → Create default VPC)" >&2; exit 1; }
SG=$(aws ec2 describe-security-groups --filters Name=group-name,Values="$NAME-web" Name=vpc-id,Values="$VPC" \
  --query 'SecurityGroups[0].GroupId' --output text)
if [ "$SG" = "None" ]; then
  SG=$(aws ec2 create-security-group --group-name "$NAME-web" --vpc-id "$VPC" \
    --description "$NAME: HTTPS and HTTP only" --query GroupId --output text)
  for port in 80 443; do
    aws ec2 authorize-security-group-ingress --group-id "$SG" --ip-permissions \
      "IpProtocol=tcp,FromPort=$port,ToPort=$port,IpRanges=[{CidrIp=0.0.0.0/0}],Ipv6Ranges=[{CidrIpv6=::/0}]" >/dev/null
  done
  aws ec2 create-tags --resources "$SG" --tags "$TAGS" "Key=Name,Value=$NAME-web"
  echo "created $SG"
else
  echo "exists"
fi

# --- Daily snapshots --------------------------------------------------------------------
say "Daily snapshots (kept 7 days)"
aws dlm create-default-role --resource-type snapshot >/dev/null 2>&1 || true
DLM_ROLE="arn:aws:iam::$ACCOUNT:role/AWSDataLifecycleManagerDefaultRole"
if [ -z "$(aws dlm get-lifecycle-policies --target-tags "Backup=$NAME" --query 'Policies[0].PolicyId' --output text 2>/dev/null | grep -v None)" ]; then
  aws dlm create-lifecycle-policy --execution-role-arn "$DLM_ROLE" --state ENABLED \
    --description "$NAME daily snapshots" --tags "Project=$NAME" --policy-details "$(cat <<EOF
{"ResourceTypes": ["VOLUME"], "TargetTags": [{"Key": "Backup", "Value": "$NAME"}],
 "Schedules": [{"Name": "daily", "CopyTags": true,
   "CreateRule": {"Interval": 24, "IntervalUnit": "HOURS", "Times": ["07:00"]},
   "RetainRule": {"Count": 7}}]}
EOF
)" >/dev/null
  echo "created (07:00 UTC every day)"
else
  echo "exists"
fi

# --- The server -------------------------------------------------------------------------
say "Server"
INSTANCE=$(aws ec2 describe-instances --filters Name=tag:Name,Values="$NAME" \
  Name=instance-state-name,Values=pending,running,stopping,stopped \
  --query 'Reservations[0].Instances[0].InstanceId' --output text)
if [ "$INSTANCE" = "None" ]; then
  AMI=$(aws ssm get-parameter --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64 \
    --query Parameter.Value --output text)
  INSTANCE=$(aws ec2 run-instances --image-id "$AMI" --instance-type "$INSTANCE_TYPE" \
    --iam-instance-profile Name="$ROLE" --security-group-ids "$SG" \
    --metadata-options HttpTokens=required,HttpEndpoint=enabled,HttpPutResponseHopLimit=1 \
    --credit-specification CpuCredits=standard \
    --disable-api-termination \
    --block-device-mappings "DeviceName=/dev/xvda,Ebs={VolumeSize=$DISK_GB,VolumeType=gp3,Encrypted=true,DeleteOnTermination=false}" \
    --tag-specifications \
      "ResourceType=instance,Tags=[{Key=Name,Value=$NAME},{Key=Project,Value=$NAME}]" \
      "ResourceType=volume,Tags=[{Key=Name,Value=$NAME},{Key=Project,Value=$NAME},{Key=Backup,Value=$NAME}]" \
    --query 'Instances[0].InstanceId' --output text)
  echo "created $INSTANCE ($INSTANCE_TYPE); waiting for it to start"
  aws ec2 wait instance-running --instance-ids "$INSTANCE"
else
  echo "exists ($INSTANCE)"
fi
save INSTANCE_ID "$INSTANCE"

# --- Fixed address ----------------------------------------------------------------------
say "Elastic IP"
ALLOC=$(aws ec2 describe-addresses --filters Name=tag:Name,Values="$NAME" --query 'Addresses[0].AllocationId' --output text)
if [ "$ALLOC" = "None" ]; then
  ALLOC=$(aws ec2 allocate-address --domain vpc \
    --tag-specifications "ResourceType=elastic-ip,Tags=[{Key=Name,Value=$NAME},{Key=Project,Value=$NAME}]" \
    --query AllocationId --output text)
fi
aws ec2 associate-address --instance-id "$INSTANCE" --allocation-id "$ALLOC" >/dev/null
IP=$(aws ec2 describe-addresses --allocation-ids "$ALLOC" --query 'Addresses[0].PublicIp' --output text)
save PUBLIC_IP "$IP"
echo "$IP"

# --- Budget alert -----------------------------------------------------------------------
say "Budget alert"
if ! aws budgets describe-budget --account-id "$ACCOUNT" --budget-name "$NAME" >/dev/null 2>&1; then
  aws budgets create-budget --account-id "$ACCOUNT" \
    --budget "{\"BudgetName\":\"$NAME\",\"BudgetLimit\":{\"Amount\":\"$BUDGET_USD\",\"Unit\":\"USD\"},\"TimeUnit\":\"MONTHLY\",\"BudgetType\":\"COST\"}" \
    --notifications-with-subscribers "$(cat <<EOF
[
 {"Notification":{"NotificationType":"ACTUAL","ComparisonOperator":"GREATER_THAN","Threshold":50,"ThresholdType":"PERCENTAGE"},
  "Subscribers":[{"SubscriptionType":"EMAIL","Address":"$BUDGET_EMAIL"}]},
 {"Notification":{"NotificationType":"ACTUAL","ComparisonOperator":"GREATER_THAN","Threshold":100,"ThresholdType":"PERCENTAGE"},
  "Subscribers":[{"SubscriptionType":"EMAIL","Address":"$BUDGET_EMAIL"}]},
 {"Notification":{"NotificationType":"FORECASTED","ComparisonOperator":"GREATER_THAN","Threshold":100,"ThresholdType":"PERCENTAGE"},
  "Subscribers":[{"SubscriptionType":"EMAIL","Address":"$BUDGET_EMAIL"}]}
]
EOF
)"
  echo "created: \$$BUDGET_USD/month, alerts to $BUDGET_EMAIL"
else
  echo "exists"
fi

DOMAIN_NOW=${DOMAIN:-${IP//./-}.sslip.io}
save DOMAIN "$DOMAIN_NOW"
say "Done"
cat <<EOF
Server $INSTANCE at $IP, address https://$DOMAIN_NOW (state in $STATE)
Next: ./aws/deploy.sh <the bundle .tgz>   (installs the app; the first run takes a few minutes)
EOF
