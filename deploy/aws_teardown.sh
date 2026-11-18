#!/usr/bin/env bash
# Remove everything aws_deploy.sh created (instance, Elastic IP, alarm, security group, key pair).
# Usage: bash deploy/aws_teardown.sh          (asks before deleting)
set -euo pipefail
export MSYS_NO_PATHCONV=1
AWS=${AWS:-aws}
command -v "$AWS" >/dev/null 2>&1 || AWS="/c/Program Files/Amazon/AWSCLIV2/aws.exe"
export AWS_DEFAULT_REGION=${REGION:-ap-south-1}
source deploy/.aws_state
read -r -p "Terminate $INSTANCE_ID and release $IP? [y/N] " ok
[ "$ok" = "y" ] || exit 0
"$AWS" cloudwatch delete-alarms --alarm-names hemosense-auto-recover
"$AWS" ec2 disassociate-address --public-ip "$IP" || true
"$AWS" ec2 release-address --allocation-id "$ALLOC"
"$AWS" ec2 terminate-instances --instance-ids "$INSTANCE_ID" >/dev/null
"$AWS" ec2 wait instance-terminated --instance-ids "$INSTANCE_ID"
"$AWS" ec2 delete-security-group --group-id "$SG"
"$AWS" ec2 delete-key-pair --key-name hemosense-key
rm -f deploy/.aws_state "$HOME/.ssh/hemosense-key.pem"
echo "All HemoSense AWS resources removed."
