# SSN Django

Sistema de gestión de operaciones financieras para presentación a la Superintendencia de Seguros de la Nación (SSN). Permite registrar, revisar y enviar operaciones semanales y mensuales (compras, ventas, canjes, plazos fijos, stocks).

## Repositorio

```bash
git clone https://git.example.com/example-org/ssn.git
git pull origin main   # actualizar
```

> Primera vez en una máquina nueva: ver [SETUP.md](https://git.example.com/example-org/workspace/raw/branch/main/SETUP.md) para configurar credenciales Git.

---

## Stack

Python 3.12+, Django 5.1+, PostgreSQL 15+, Gunicorn, WhiteNoise, Tailwind CSS (via django-tailwind).

---

## Configuración

```bash
cp .env.example .env
# Completar: SECRET_KEY, SSN_API_*, POSTGRES_PASSWORD, DJANGO_SUPERUSER_PASSWORD
```

Variables críticas:

| Variable | Descripción |
|----------|-------------|
| `SECRET_KEY` | Clave secreta Django. Generar: `openssl rand -hex 32` |
| `SSN_API_USERNAME/PASSWORD/CIA` | Credenciales de la compañía ante la SSN |
| `SSN_API_BASE_URL` | `https://ri.ssn.gob.ar/api` (prod) · `https://testri.ssn.gob.ar/api` (test) |
| `POSTGRES_PASSWORD` | Contraseña PostgreSQL |
| `IDENTITY_SERVICE_URL` | `http://identity_api:8080` (con identity) · vacío (modo local) |
| `SSL_DOMAIN` | Dominio para routing Traefik |

---

## Docker

```bash
# Producción detrás de Traefik (modo habitual)
docker compose --env-file .env -f docker/docker-compose.prod.traefik.yml up -d --build

# Con Nginx adicional (override)
docker compose --env-file .env \
  -f docker/docker-compose.prod.traefik.yml \
  -f docker/docker-compose.prod.traefik.nginx.yml \
  up -d --build

# Standalone con Nginx + SSL propio
docker compose --env-file .env -f docker/docker-compose.prod.standalone.yml up -d --build

# Migraciones
docker exec -it reports_web python ssn/manage.py migrate
```

### Compose variants

```
docker/
├── Dockerfile              # Dev (runserver)
├── Dockerfile.prod         # Prod (gunicorn + WhiteNoise)
├── Dockerfile.nginx        # Nginx con SSL (standalone)
├── docker-compose.dev.yml
├── docker-compose.prod.standalone.yml   # Con Nginx + SSL propio
├── docker-compose.prod.traefik.yml      # Detrás de Traefik (WhiteNoise)
├── docker-compose.prod.traefik.nginx.yml  # Override: agrega Nginx al modo Traefik
└── nginx/
```

---

## Desarrollo local

```bash
python -m venv venv
source venv/bin/activate       # Linux/Mac
.\venv\Scripts\Activate.ps1   # Windows

pip install -r requirements.txt

cp .env.example .env
# Editar: DJANGO_SETTINGS_MODULE=config.settings.dev

cd ssn
python manage.py migrate
python manage.py tailwind install
python manage.py tailwind build

python manage.py runserver
```

> `config.settings.dev` usa SQLite local y DEBUG=True.

---

## Autenticación

Dos modos detectados automáticamente según `IDENTITY_SERVICE_URL`:

| Modo | `IDENTITY_SERVICE_URL` | Descripción |
|------|------------------------|-------------|
| Local | vacío | Usuarios en BD de Django. Superusuario creado al iniciar el container. |
| Identidad | `http://identity_api:8080` | Autenticación contra el servicio `identity`. Los usuarios se sincronizan en el primer login. |

---

## Traefik routing

SSN usa **Host routing** (no PathPrefix) porque es una app Django con templates.

| Request | Servicio | Regla |
|---------|----------|-------|
| `/identity/*` | identity FastAPI | PathPrefix (mayor prioridad) |
| `/mailsender/*` | mailsender FastAPI | PathPrefix (mayor prioridad) |
| `/*` (resto) | SSN Django | Host match |

---

## Comandos de gestión

```bash
# Migraciones
docker exec -it reports_web python ssn/manage.py migrate

# Limpiar solicitudes vacías (> 7 días)
docker exec -it reports_web python ssn/manage.py clean_requests --days 7

# Limpiar previews Excel (> 1 hora)
docker exec -it reports_web python ssn/manage.py clean_preview_excels --hours 1

# Sincronizar histórico desde API SSN
docker exec -it reports_web python ssn/manage.py sync_ssn_data --period semanal --year 2025
docker exec -it reports_web python ssn/manage.py sync_ssn_data --period mensual --year 2025

# Alertas de vencimientos (configurar como cron diario)
docker exec -it reports_web python ssn/manage.py send_deadline_alerts
docker exec -it reports_web python ssn/manage.py send_deadline_alerts --dry-run
docker exec -it reports_web python ssn/manage.py send_deadline_alerts --level danger
```

---

## Estructura del proyecto

```
ssn/
├── manage.py
├── apps/
│   ├── accounts/        # Autenticación y usuarios
│   ├── operaciones/     # Operaciones financieras (modelos, servicios, vistas)
│   │   ├── models/
│   │   │   ├── semanal/ # Compra, venta, canje, plazo fijo
│   │   │   └── mensual/ # Stocks (inversión, plazo fijo, cheque PD)
│   │   ├── services/
│   │   ├── helpers/
│   │   └── management/  # Comandos clean_requests, sync_ssn_data, send_deadline_alerts
│   ├── ssn_client/      # Cliente para API SSN
│   └── theme/           # Tailwind CSS + templates base
└── config/
    ├── settings/
    │   ├── base.py
    │   ├── dev.py
    │   └── prod.py
    └── urls.py
```

---

## Troubleshooting

### Loop infinito de login

`IDENTITY_SERVICE_URL` apunta a `localhost` dentro del container.  
Fix: usar `http://identity_api:8080` (nombre del container en red Docker).

### Tailwind no compila en prod

WhiteNoise sirve el CSS ya compilado. Si hay cambios en templates, compilar antes del build:
```bash
cd ssn && python manage.py tailwind build
```

### `python-magic` falla en Windows (desarrollo local)

```bash
pip uninstall python-magic
pip install python-magic-bin
```
