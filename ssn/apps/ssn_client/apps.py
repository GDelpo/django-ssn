import logging

from django.apps import AppConfig
from django.conf import settings

logger = logging.getLogger("ssn_client")


class SsnClientConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ssn_client"
    ssn_client = None

    def ready(self):
        if not getattr(settings, "SSN_API_ENABLED", True):
            logger.info(
                "SSN client deshabilitado por configuracion (SSN_API_ENABLED=False)."
            )
            return

        has_credentials = (
            hasattr(settings, "SSN_API_USERNAME")
            and settings.SSN_API_USERNAME
            and hasattr(settings, "SSN_API_PASSWORD")
            and settings.SSN_API_PASSWORD
        )

        if not has_credentials:
            logger.info(
                "No se inicializa el cliente SSN: faltan credenciales o estamos en un entorno de build/migración."
            )
            return

        # Si ya está inicializado, no hacer nada.
        if SsnClientConfig.ssn_client:
            return

        try:
            # Importamos el servicio para evitar importaciones circulares
            from .clients import SsnService

            SsnClientConfig.ssn_client = SsnService(
                username=settings.SSN_API_USERNAME,
                password=settings.SSN_API_PASSWORD,
                cia=settings.SSN_API_CIA,
                base_url=settings.SSN_API_BASE_URL,
                max_retries=settings.SSN_API_MAX_RETRIES,
                retry_delay=settings.SSN_API_RETRY_DELAY,
                verify_ssl=getattr(settings, "SSN_API_VERIFY_SSL", True),
                request_timeout=getattr(settings, "SSN_API_REQUEST_TIMEOUT", (10, 20)),
            )
            logger.info("Cliente SSN inicializado exitosamente.")
        except Exception as e:
            logger.warning(f"No se pudo inicializar el cliente SSN: {e}")
