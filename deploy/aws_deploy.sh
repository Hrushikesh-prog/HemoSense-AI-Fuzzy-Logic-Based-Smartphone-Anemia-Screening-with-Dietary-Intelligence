#!/usr/bin/env bash
# HemoSense API -> AWS (ap-south-1). Idempotent: the first run provisions, later runs
# only re-upload the code and restart the stack.
#
# Architecture: 1x EC2 t3.small (Ubuntu 24.04, encrypted gp3, IMDSv2 only) + Elastic IP,
# Docker Compose [api + Caddy]. Caddy terminates TLS with a Let's Encrypt certificate for
# <ip-with-dashes>.sslip.io and also serves plain HTTP on the bare IP as a fallback.
# Security group: 80/443 public, 22 only from the deployer's current IP.
# CloudWatch alarm auto-recovers the instance if the AWS host fails its status check.
#
# Needs: AWS CLI v2 credentials with deploy/iam-policy.json, ssh/scp, tar, curl.
# Usage (Git Bash, repo root):  bash deploy/aws_deploy.sh
# Tear down after the demo:     bash deploy/aws_teardown.sh
set -euo pipefail
export MSYS_NO_PATHCONV=1   # stop Git Bash rewriting /aws/... and file:// paths

AWS=${AWS:-aws}
command -v "$AWS" >/dev/null 2>&1 || AWS="/c/Program Files/Amazon/AWSCLIV2/aws.exe"
REGION=${REGION:-ap-south-1}
NAME=hemosense
TYPE=${TYPE:-t3.small}
KEY="$HOME/.ssh/${NAME}-key.pem"
STATE=deploy/.aws_state
SSH_OPTS=(-o StrictHostKeyChecking=accept-new -o ConnectTimeout=8 -i "$KEY")
export AWS_DEFAULT_REGION=$REGION
aws_() { "$AWS" "$@"; }

[ -f models/anfis.json ] || { echo "models/anfis.json missing: run python -m research.run_experiment"; exit 1; }
[ -f "$STATE" ] && source "$STATE"

if [ -z "${INSTANCE_ID:-}" ]; then
  echo "== key pair"
  mkdir -p "$HOME/.ssh"
  if [ ! -f "$KEY" ]; then
    aws_ ec2 create-key-pair --key-name "${NAME}-key" --key-type ed25519 \
      --tag-specifications "ResourceType=key-pair,Tags=[{Key=Project,Value=${NAME}}]" \
      --query KeyMaterial --output text | tr -d '
' > "$KEY"   # strip Windows CRLF
    chmod 600 "$KEY"
  fi

  echo "== security group"
  VPC=$(aws_ ec2 describe-vpcs --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text)
  SG=$(aws_ ec2 create-security-group --group-name "${NAME}-sg" --description "HemoSense API: 80/443 public, 22 deployer only" \
        --vpc-id "$VPC" --tag-specifications "ResourceType=security-group,Tags=[{Key=Project,Value=${NAME}}]" \
        --query GroupId --output text)
  MYIP=$(curl -s https://checkip.amazonaws.com | tr -d '\r\n')
  aws_ ec2 authorize-security-group-ingress --group-id "$SG" --protocol tcp --port 22 --cidr "${MYIP}/32" >/dev/null
  aws_ ec2 authorize-security-group-ingress --group-id "$SG" --protocol tcp --port 80 --cidr 0.0.0.0/0 >/dev/null
  aws_ ec2 authorize-security-group-ingress --group-id "$SG" --protocol tcp --port 443 --cidr 0.0.0.0/0 >/dev/null

  echo "== instance ($TYPE)"
  AMI=$(aws_ ssm get-parameter --name /aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id \
        --query Parameter.Value --output text)
  cat > deploy/user-data.sh <<'UD'
#!/bin/bash
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y docker.io docker-compose-v2 unattended-upgrades
systemctl enable --now docker
usermod -aG docker ubuntu
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile && echo '/swapfile none swap sw 0 0' >> /etc/fstab
touch /var/lib/cloud/instance/hemosense-ready
UD
  INSTANCE_ID=$(aws_ ec2 run-instances --image-id "$AMI" --instance-type "$TYPE" --key-name "${NAME}-key" \
      --security-group-ids "$SG" --user-data file://deploy/user-data.sh \
      --metadata-options "HttpTokens=required,HttpEndpoint=enabled,HttpPutResponseHopLimit=2" \
      --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=20,VolumeType=gp3,Encrypted=true,DeleteOnTermination=true}' \
      --credit-specification CpuCredits=unlimited \
      --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=${NAME}},{Key=Project,Value=${NAME}}]" \
                           "ResourceType=volume,Tags=[{Key=Project,Value=${NAME}}]" \
      --query 'Instances[0].InstanceId' --output text)
  printf 'INSTANCE_ID=%s\nSG=%s\n' "$INSTANCE_ID" "$SG" > "$STATE"
  aws_ ec2 wait instance-running --instance-ids "$INSTANCE_ID"

  echo "== elastic ip"
  ALLOC=$(aws_ ec2 allocate-address --domain vpc \
          --tag-specifications "ResourceType=elastic-ip,Tags=[{Key=Project,Value=${NAME}}]" --query AllocationId --output text)
  aws_ ec2 associate-address --instance-id "$INSTANCE_ID" --allocation-id "$ALLOC" >/dev/null
  IP=$(aws_ ec2 describe-addresses --allocation-ids "$ALLOC" --query 'Addresses[0].PublicIp' --output text)
  printf 'INSTANCE_ID=%s\nSG=%s\nALLOC=%s\nIP=%s\n' "$INSTANCE_ID" "$SG" "$ALLOC" "$IP" > "$STATE"

  echo "== auto-recover alarm"
  aws_ cloudwatch put-metric-alarm --alarm-name "${NAME}-auto-recover" \
    --alarm-description "Recover HemoSense EC2 if the AWS host fails" \
    --namespace AWS/EC2 --metric-name StatusCheckFailed_System --statistic Maximum \
    --dimensions Name=InstanceId,Value="$INSTANCE_ID" --period 60 --evaluation-periods 2 \
    --threshold 1 --comparison-operator GreaterThanOrEqualToThreshold \
    --alarm-actions "arn:aws:automate:${REGION}:ec2:recover"

  echo "== waiting for the host to finish installing Docker (2-4 min)"
  for i in $(seq 1 60); do
    ssh "${SSH_OPTS[@]}" ubuntu@"$IP" 'test -f /var/lib/cloud/instance/hemosense-ready' >/dev/null 2>&1 && break
    sleep 8
  done
fi

echo "== waiting for SSH + Docker on $IP"
for i in $(seq 1 60); do
  ssh "${SSH_OPTS[@]}" ubuntu@"$IP" 'test -f /var/lib/cloud/instance/hemosense-ready' >/dev/null 2>&1 && break
  [ "$i" = 60 ] && { echo "host not ready"; exit 1; }
  sleep 8
done

HOST="$(echo "$IP" | tr . -).sslip.io"
echo "== upload code to $IP"
tar czf deploy/bundle.tgz Dockerfile .dockerignore hemosense api/*.py api/requirements-serve.txt \
    models/anfis.json models/confidence.json models/rag_index.json deploy/docker-compose.yml deploy/Caddyfile
scp "${SSH_OPTS[@]}" deploy/bundle.tgz ubuntu@"$IP":/home/ubuntu/bundle.tgz
if [ -f api/.env ]; then
  grep -v '^HEMOSENSE_MODEL_PATH=' api/.env > deploy/.hemosense.env
else
  : > deploy/.hemosense.env
fi
echo "HEMOSENSE_CORS_ORIGINS=*" >> deploy/.hemosense.env
scp "${SSH_OPTS[@]}" deploy/.hemosense.env ubuntu@"$IP":/home/ubuntu/hemosense.env
rm -f deploy/.hemosense.env

echo "== build + start (api + caddy)"
ssh "${SSH_OPTS[@]}" ubuntu@"$IP" "SITE_HOST=$HOST PUBLIC_IP=$IP bash -s" <<'REMOTE'
set -e
chmod 600 ~/hemosense.env
rm -rf ~/hemosense && mkdir -p ~/hemosense && tar xzf ~/bundle.tgz -C ~/hemosense
cd ~/hemosense/deploy
printf 'SITE_HOST=%s\nPUBLIC_IP=%s\n' "$SITE_HOST" "$PUBLIC_IP" > .env
sudo docker compose up -d --build --remove-orphans
for i in $(seq 1 30); do curl -fs http://127.0.0.1/health -H "Host: $PUBLIC_IP" >/dev/null && break; sleep 3; done
sudo docker compose ps
REMOTE

echo
echo "== smoke test from here"
curl -s --max-time 20 "https://$HOST/health" | head -c 300 || true; echo
curl -s --max-time 10 "http://$IP/health" | head -c 120 || true; echo
echo
echo "App > Settings > Backend URL:   https://$HOST"
echo "Fallback (plain HTTP):          http://$IP"
