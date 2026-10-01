# Minerals Chain

B2B marketplace for Saudi industrial minerals — verified sellers, identity-protected RFQs and quotations, lab verification and Mineral Passports, orders with shipments and documents, disputes, subscriptions, bilingual (EN/AR) portals for admins, sellers, buyers and labs.

**Stack:** FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL 16 · Redis · Jinja2 · Bootstrap · ECharts · gunicorn/uvicorn · nginx


## Run locally (Windows / Laragon)
```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env          # then set DATABASE_URL
alembic upgrade head
python scripts/load_master_data.py
python scripts/seed_test_data.py   # test accounts, password admin123 (dev only)
python -m uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000 — `admin@mineralstest.com`, `seller@mineralstest.com`, `buyer@mineralstest.com`, `lab@mineralstest.com`.

## Before every release
```powershell
pytest tests/ -q
python scripts/check_routes.py
python scripts/security_selftest.py
```

## Deploy
See `docs/DEPLOYMENT.md`. In short, on an Ubuntu 24.04 server:
```bash
sudo bash deploy/server_setup.sh mineralschain.sa it@mineralschain.sa   # once
sudo bash deploy/first_deploy.sh mineralschain.sa it@mineralschain.sa   # once
sudo bash deploy/deploy.sh v1.1                                          # every update
```
