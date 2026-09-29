#!/usr/bin/env bash
# Usage (as root, Ubuntu 24.04):  bash deploy/server_setup.sh mineralschain.sa admin@mineralschain.sa
set -euo pipefail

DOMAIN="${1:?domain required}"
EMAIL="${2:?email for Let's Encrypt required}"
APP_USER=minerals
BASE=/srv/minerals
APP_DIR=$BASE/app
DB_NAME=minerals_chain
DB_USER=minerals
DB_PASS="$(openssl rand -hex 24)"

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  python3 python3-venv python3-dev build-essential libpq-dev \
  postgresql postgresql-contrib redis-server nginx certbot python3-certbot-nginx \
  ufw fail2ban unattended-upgrades git curl

timedatectl set-timezone Asia/Riyadh

id -u $APP_USER >/dev/null 2>&1 || useradd --system --create-home --home-dir $BASE --shell /bin/bash $APP_USER
mkdir -p $APP_DIR /var/backups/minerals-chain /var/www/certbot
chown -R $APP_USER:$APP_USER $BASE /var/backups/minerals-chain
chmod 750 $BASE /var/backups/minerals-chain

sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE ROLE $DB_USER LOGIN PASSWORD '$DB_PASS';"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER ENCODING 'UTF8' TEMPLATE template0;"

sed -i 's/^#\?\s*supervised .*/supervised systemd/' /etc/redis/redis.conf
sed -i 's/^#\?\s*bind .*/bind 127.0.0.1 ::1/' /etc/redis/redis.conf
systemctl enable --now redis-server postgresql

ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable
systemctl enable --now fail2ban

echo
echo "================================================================"
echo " Server prepared."
echo " DATABASE_URL=postgresql://$DB_USER:$DB_PASS@127.0.0.1:5432/$DB_NAME"
echo " Save that line now — it is not stored anywhere else."
echo " Next: copy the code to $APP_DIR, then run deploy/first_deploy.sh $DOMAIN $EMAIL"
echo "================================================================"
