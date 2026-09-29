#!/usr/bin/env bash
# Usage (as root, for every update after the first):  bash deploy/deploy.sh [git-ref]
set -euo pipefail

BASE=/srv/minerals
APP_DIR=$BASE/app
REF="${1:-}"
cd $APP_DIR

sudo -u minerals $BASE/venv/bin/python scripts/run_scheduled_jobs.py --job backup

if [ -d .git ] && [ -n "$REF" ]; then
  sudo -u minerals git fetch --all --tags
  sudo -u minerals git checkout "$REF"
fi

sudo -u minerals $BASE/venv/bin/pip install -r requirements.txt
sudo -u minerals $BASE/venv/bin/alembic upgrade head
sudo -u minerals $BASE/venv/bin/python scripts/load_master_data.py

systemctl reload minerals.service || systemctl restart minerals.service
sleep 3
curl -fsS http://127.0.0.1:8000/healthz && echo
echo "Deployed. Logs: journalctl -u minerals -f"
