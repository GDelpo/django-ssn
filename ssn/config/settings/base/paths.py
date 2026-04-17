import os
import sys
from pathlib import Path

from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

# Añadir directorio de apps al path
APPS_DIR = BASE_DIR / "apps"
sys.path.insert(0, str(APPS_DIR))

# Directorios de Media, Static y Logs
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"
# Static files collected OUTSIDE ssn/ directory (at project root level)
# Docker: /app/static  |  Local: <project_root>/static
STATIC_ROOT = BASE_DIR.parent / "static"
STATIC_URL = "/static/"
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# WhiteNoise: serve static files directly from Gunicorn
# Works transparently - if Nginx is in front, it serves static first;
# if not, WhiteNoise handles it with compression and caching.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
