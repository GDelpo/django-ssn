# 1. Definir PRIMERO las variables dummy que `custom.py` necesita
SSN_API_USERNAME = "build_user"
SSN_API_PASSWORD = "build_pass"
SSN_API_CIA = "build_cia"
SSN_API_BASE_URL = "https://build-example.com"
SSN_API_ENABLED = False
SECRET_KEY = "dummy_secret_for_build_purposes_only"

# 2. Importar la configuración base DESPUÉS
# Ahora, cuando se importe custom.py, las variables de arriba ya existirán
from .base import *

# 3. Sobrescribir el resto de la configuración específica para el build
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db_build.sqlite3",
    }
}

CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
