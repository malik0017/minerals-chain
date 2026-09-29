#!/usr/bin/env bash
# Usage (as root, after the code is in /srv/minerals/app and .env is filled):
#   bash deploy/first_deploy.sh mineralschain.sa admin@mineralschain.sa
set -euo pipefail

DOMAIN="${1:?domain required}"
EMAIL="${2:?email required}"
BASE=/srv/minerals
APP_DIR=$BASE/app
cd $APP_DIR

test -f .env || { echo ".env missing — copy .env.production.example to .env and fill it"; exit 1; }
chown -R minerals:minerals $BASE
chmod 600 .env

sudo -u minerals python3 -m venv $BASE/venv
sudo -u minerals $BASE/venv/bin/pip install --upgrade pip wheel
sudo -u minerals $BASE/venv/bin/pip install -r requirements.txt

sudo -u minerals $BASE/venv/bin/python scripts/harden_env.py --profile production --redis redis://127.0.0.1:6379/0 || true
sudo -u minerals $BASE/venv/bin/python -c "from app.core.config import settings; from app.core.production import problems; f,w=problems(settings); print('\n'.join(['FATAL: '+x for x in f]+['warn: '+x for x in w]) or 'config ok'); raise SystemExit(1 if f else 0)"

sudo -u minerals mkdir -p storage app/static/uploads/avatars
sudo -u minerals $BASE/venv/bin/alembic upgrade head
sudo -u minerals $BASE/venv/bin/python scripts/load_master_data.py

sed "s/mineralschain.sa/$DOMAIN/g" deploy/nginx/minerals.conf > /etc/nginx/sites-available/minerals.conf
cp deploy/nginx/minerals-proxy.conf /etc/nginx/snippets/minerals-proxy.conf
ln -sf /etc/nginx/sites-available/minerals.conf /etc/nginx/sites-enabled/minerals.conf
rm -f /etc/nginx/sites-enabled/default

if [ ! -d /etc/letsencrypt/live/$DOMAIN ]; then
  cat > /etc/nginx/sites-enabled/minerals.conf <<NGX
server { listen 80; server_name $DOMAIN www.$DOMAIN; location /.well-known/acme-challenge/ { root /var/www/certbot; } }
NGX
  nginx -t && systemctl reload nginx
  certbot certonly --webroot -w /var/www/certbot -d $DOMAIN -d www.$DOMAIN --email $EMAIL --agree-tos --non-interactive
  ln -sf /etc/nginx/sites-available/minerals.conf /etc/nginx/sites-enabled/minerals.conf
fi
nginx -t && systemctl reload nginx

cp deploy/systemd/minerals.service deploy/systemd/minerals-jobs.service deploy/systemd/minerals-jobs.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now minerals.service minerals-jobs.timer

sleep 3
curl -fsS http://127.0.0.1:8000/healthz && echo
echo "Live at https://$DOMAIN — create the first admin with: sudo -u minerals $BASE/venv/bin/python scripts/create_admin.py"
