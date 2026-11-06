# django-ssn

<p>
  <img alt="Django" src="https://img.shields.io/badge/django-5.1%2B-092E20?logo=django&logoColor=white">
  <img alt="Python" src="https://img.shields.io/badge/python-3.12%2B-blue?logo=python&logoColor=white">
  <img alt="PostgreSQL" src="https://img.shields.io/badge/postgresql-15%2B-336791?logo=postgresql&logoColor=white">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-green">
</p>

> Django app to manage financial operations and file presentations with the Argentine SSN (Superintendencia de Seguros de la Nación).

Targeted at insurance companies subject to SSN oversight: registers weekly and monthly operations (buys, sells, swaps, fixed-term deposits, stocks) and submits them to the SSN API (`ri.ssn.gob.ar`).

## Features

- Weekly and monthly operation registration (compras, ventas, canjes, plazos fijos, stocks).
- Submission to SSN API with retries and validation.
- Historical sync from SSN API (`sync_ssn_data` management command).
- Deadline alerts by email (`send_deadline_alerts`).
- Excel export of a request preview before submitting it.
- Two auth modes: local Django DB or delegation to an external identity service.

## Quickstart

### Requirements

- Python 3.12 (pinned `pandas` does not build on 3.14)
- PostgreSQL 15+ (production) or SQLite (dev)
- Node.js (for Tailwind build via `django-tailwind`)
- Valid SSN API credentials (`SSN_API_USERNAME`, `SSN_API_PASSWORD`, `SSN_API_CIA`)

### Install (local dev)

```bash
git clone https://github.com/GDelpo/django-ssn.git
cd django-ssn

python -m venv env
source env/bin/activate          # Linux/Mac
# .\env\Scripts\Activate.ps1     # Windows

pip install -r requirements.txt
```

### Configure

```bash
cp .env.example .env
# Edit .env: fill SECRET_KEY, SSN_API_*, POSTGRES_PASSWORD, etc.
# For dev with SQLite, set DJANGO_SETTINGS_MODULE=config.settings.dev, USE_SQLITE=True and DEBUG=True.
# POSTGRES_DB, POSTGRES_USER and POSTGRES_PASSWORD are read anyway: any value works with SQLite.
```

See [Configuration](#configuration) below for the full list.

### Run (local dev)

```bash
cd ssn
python manage.py migrate
python manage.py tailwind install
python manage.py tailwind build
python manage.py runserver
```

### Run (production, Docker + Traefik)

```bash
docker compose --env-file .env -f docker/docker-compose.prod.traefik.yml up -d --build
docker exec -it reports_web python ssn/manage.py migrate
```

Other compose variants:

```
docker/
├── docker-compose.dev.yml                    # Dev
├── docker-compose.prod.standalone.yml        # Nginx + own SSL
├── docker-compose.prod.traefik.yml           # Behind Traefik (WhiteNoise)
└── docker-compose.prod.traefik.nginx.yml     # Override: adds Nginx to Traefik mode
```

## Configuration

Variables live in `.env` (copy from `.env.example`):

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret. Generate with `openssl rand -hex 32`. | — |
| `DEBUG` | Debug mode. | `False` |
| `ALLOWED_HOSTS` | Comma-separated hostnames. | — |
| `SSN_API_USERNAME` | SSN API username. | — |
| `SSN_API_PASSWORD` | SSN API password. | — |
| `SSN_API_CIA` | SSN company code assigned to your insurer. | — |
| `SSN_API_BASE_URL` | `https://ri.ssn.gob.ar/api` (prod) or `https://testri.ssn.gob.ar/api` (test). | — |
| `POSTGRES_*` | PostgreSQL connection (`DB`, `USER`, `PASSWORD`, `HOST`, `PORT`). | — |
| `COMPANY_NAME` / `COMPANY_WEBSITE` / `COMPANY_LOGO_URL` | Branding rendered in templates. | placeholders |
| `SUPPORT_EMAIL` | Support contact shown in error pages. | `support@example.com` |
| `IDENTITY_SERVICE_URL` | External identity service URL. Empty = local DB auth. | empty |
| `SSL_DOMAIN` | Host for Traefik routing. | — |

## Authentication

Two modes, selected automatically via `IDENTITY_SERVICE_URL`:

| Mode | `IDENTITY_SERVICE_URL` | Description |
|------|------------------------|-------------|
| Local | empty | Users in Django DB. Superuser is auto-created by `entrypoint.sh` from `DJANGO_SUPERUSER_*` vars. |
| External | URL | Authenticates against an external identity service (expects a FastAPI-style `/api/v1/me` endpoint). Users sync on first login. |

## Management commands

```bash
# Migrations
python ssn/manage.py migrate

# Cleanup empty requests (> 7 days)
python ssn/manage.py clean_requests --days 7

# Cleanup preview Excels (> 1 hour)
python ssn/manage.py clean_preview_excels --hours 1

# Sync history from SSN API
python ssn/manage.py sync_ssn_data --period semanal --year 2025
python ssn/manage.py sync_ssn_data --period mensual --year 2025

# Send deadline alerts (schedule as daily cron)
python ssn/manage.py send_deadline_alerts
python ssn/manage.py send_deadline_alerts --dry-run
python ssn/manage.py send_deadline_alerts --level danger
```

## Tests

```bash
cd ssn
python manage.py test
```

Uses the variables above; no database server or `collectstatic` is needed with `USE_SQLITE=True`. Coverage is limited to `accounts` (login, logout, profile and auth backends): operations and the SSN client have no automated tests yet.

## Architecture

```
ssn/
├── manage.py
├── apps/
│   ├── accounts/        # Auth and users
│   ├── operaciones/     # Financial operations (models, services, views)
│   │   ├── models/
│   │   │   ├── semanal/ # Buy, sell, swap, fixed-term
│   │   │   └── mensual/ # Stocks (investment, fixed-term, postdated check)
│   │   ├── services/
│   │   ├── helpers/
│   │   └── management/  # clean_requests, sync_ssn_data, send_deadline_alerts
│   ├── ssn_client/      # SSN API client
│   └── theme/           # Tailwind CSS + base templates
└── config/
    ├── settings/
    │   ├── base/
    │   ├── dev.py
    │   └── prod.py
    └── urls.py
```

## Troubleshooting

**Infinite login loop** — `IDENTITY_SERVICE_URL` points to `localhost` inside the container. Use the container name on the Docker network (e.g. `http://identity_api:8080`).

**Tailwind not compiling in prod** — WhiteNoise serves pre-built CSS. Rebuild before building the image:
```bash
cd ssn && python manage.py tailwind build
```

**`python-magic` fails on Windows (local dev)**:
```bash
pip uninstall python-magic
pip install python-magic-bin
```

## Notes

- The SSN API is specific to Argentine insurance regulation — this app is useful only for companies reporting to the Superintendencia de Seguros de la Nación.
- Field names, forms, and business rules mirror SSN requirements and are in Spanish, by design.

## License

[MIT](LICENSE) (c) 2026 Guido Delponte
