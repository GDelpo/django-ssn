from decouple import config

from .base import *

# --- SOBREESCRIBIR PARA DESARROLLO ---
DEBUG = config("DEBUG", default=False, cast=bool)
SECRET_KEY = config("SECRET_KEY", default="django-insecure-dev-key-para-desarrollo")
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "web"]

# --- Database ---
# En Docker usamos PostgreSQL (heredado de base), solo usar SQLite si se indica explícitamente
USE_SQLITE = config("USE_SQLITE", default=False, cast=bool)
if USE_SQLITE:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db_dev.sqlite3",
        }
    }
# Si no, usa la configuración de PostgreSQL de base/database.py

# Relajar seguridad para desarrollo
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0

# Cargar configuración de Logging para el modo DEBUG
LOGGING = get_logging_config(debug_mode=DEBUG, logs_dir=LOGS_DIR, apps=LOGGING_APPS)
