import os

from decouple import config

# --- SSN Client Configuration ---
# Usamos decouple directamente, sin parámetros inventados.
SSN_API_USERNAME = config("SSN_API_USERNAME")
SSN_API_PASSWORD = config("SSN_API_PASSWORD")
SSN_API_CIA = config("SSN_API_CIA")
SSN_API_BASE_URL = config("SSN_API_BASE_URL")
SSN_API_MAX_RETRIES = config("SSN_API_MAX_RETRIES", default=3, cast=int)
SSN_API_RETRY_DELAY = config("SSN_API_RETRY_DELAY", default=5, cast=int)
SSN_API_ENABLED = config("SSN_API_ENABLED", default=True, cast=bool)
SSN_API_VERIFY_SSL = config("SSN_API_VERIFY_SSL", default=True, cast=bool)  # False para test con cert self-signed

# --- Authentication Configuration ---
# Solo necesitas configurar IDENTITY_SERVICE_URL
# - No lo configures: autenticación local (base de datos Django)
# - Configúralo: autenticación centralizada (servicio FastAPI)
IDENTITY_SERVICE_URL = config("IDENTITY_SERVICE_URL", default="")

# SSL verification for Identity Service (solo si usas servicio externo)
IDENTITY_SERVICE_VERIFY_SSL = config(
    "IDENTITY_SERVICE_VERIFY_SSL",
    default=True,
    cast=bool,
)

# --- Otras configuraciones ---
PREVIEW_MAX_AGE_MINUTES = config("PREVIEW_MAX_AGE_MINUTES", default=5, cast=int)
LOGGING_APPS = ["operaciones", "ssn_client", "accounts"]
SUPPORT_EMAIL = config("SUPPORT_EMAIL", default="soporte@compania.com")

# --- Configuraciones de Terceros ---
TAILWIND_APP_NAME = "theme"
INTERNAL_IPS = ["127.0.0.1"]
NPM_BIN_PATH = "C:/Program Files/nodejs/npm.cmd" if os.name == "nt" else "/usr/local/bin/npm"
REST_FRAMEWORK = {"DEFAULT_THROTTLE_RATES": {"anon": "100/day", "user": "1000/day"}}

# --- Configuración de la Compañía ---
COMPANY_NAME = config("COMPANY_NAME", default="Nombre Compañía")
COMPANY_WEBSITE = config("COMPANY_WEBSITE", default="https://www.compania.com")
COMPANY_LOGO_URL = config(
    "COMPANY_LOGO_URL", default="https://www.compania.com/logo.png"
)
COMPANY_FAVICON_URL = config(
    "COMPANY_FAVICON_URL", default="https://www.compania.com/favicon.ico"
)
BASE_URL = config("BASE_URL", default="")

# --- Email de Alertas SSN ---
# MAILSENDER_URL vacío → usa Django SMTP nativo
# MAILSENDER_URL configurado → usa el servicio Mailsender interno (HTTP API)
# El servicio SSN se autentica en identity con sus propias credenciales de servicio
# y usa el token JWT resultante para llamar a Mailsender.
MAILSENDER_URL = config("MAILSENDER_URL", default="")
MAILSENDER_SERVICE_USER = config("MAILSENDER_SERVICE_USER", default="")
MAILSENDER_SERVICE_PASSWORD = config("MAILSENDER_SERVICE_PASSWORD", default="")
ALERT_EMAIL_RECIPIENTS = config("ALERT_EMAIL_RECIPIENTS", default="")  # CSV: a@x.com,b@x.com

# --- Caché cross-process para alertas ---
# FileBasedCache permite compartir estado entre el web server (gunicorn) y el cron.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    },
    "alerts": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": "/tmp/ssn_alerts_cache",
    },
}
