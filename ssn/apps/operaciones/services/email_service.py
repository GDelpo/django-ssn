"""
Servicio de envío de emails para el sistema SSN.

Dual-mode (mismo patrón que IDENTITY_SERVICE_URL en accounts/services.py):
- MAILSENDER_URL vacío  → Django SMTP nativo (send_mail)
- MAILSENDER_URL set    → Servicio Mailsender interno (HTTP API)

Cuando usa Mailsender, primero se autentica en identity con las credenciales
de servicio SSN (MAILSENDER_SERVICE_USER / MAILSENDER_SERVICE_PASSWORD) para
obtener un JWT, y lo adjunta como Bearer token al llamar al endpoint de emails.
Mismo patrón que el resto de los clientes internos.

El from_email no se pasa: Mailsender usa el sender configurado en SendGrid por defecto.

Throttle de alertas: un email de vencimientos por día vía FileBasedCache ("alerts" backend).
"""

import datetime
import logging
import time as _time
from typing import List, Optional

import requests
from django.conf import settings
from django.core.cache import caches
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from operaciones.services.alert_service import Alert, AlertLevel

logger = logging.getLogger("operaciones")

_THROTTLE_KEY_PREFIX = "ssn_alert_email_sent"

# Caché en memoria del token de servicio (dentro del proceso del management command).
_service_token: Optional[str] = None
_service_token_fetched_at: float = 0.0
_SERVICE_TOKEN_TTL = 50 * 60  # 50 minutos de margen (tokens de servicio duran 365 días)


def _throttle_key() -> str:
    return f"{_THROTTLE_KEY_PREFIX}_{datetime.date.today().isoformat()}"


def _get_service_token(identity_url: str, username: str, password: str) -> str:
    """
    Obtiene un JWT de servicio desde identity, con caché en memoria.
    Reutiliza el token mientras siga vigente.
    """
    global _service_token, _service_token_fetched_at

    if _service_token and (_time.monotonic() - _service_token_fetched_at) < _SERVICE_TOKEN_TTL:
        return _service_token

    login_url = f"{identity_url.rstrip('/')}/login"
    response = requests.post(
        login_url,
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    response.raise_for_status()
    token = response.json().get("access_token", "")
    if not token:
        raise ValueError("identity no retornó access_token")

    _service_token = token
    _service_token_fetched_at = _time.monotonic()
    logger.debug("ssn email: token de servicio obtenido para %s", username)
    return token


def _post_to_mailsender(payload: dict, mailsender_url: str) -> None:
    """Autentica en identity y hace POST al endpoint de emails de Mailsender."""
    identity_url = getattr(settings, "IDENTITY_SERVICE_URL", "").strip()
    service_user = getattr(settings, "MAILSENDER_SERVICE_USER", "").strip()
    service_password = getattr(settings, "MAILSENDER_SERVICE_PASSWORD", "").strip()

    if not all([identity_url, service_user, service_password]):
        raise ValueError(
            "Para usar Mailsender configurar: IDENTITY_SERVICE_URL, "
            "MAILSENDER_SERVICE_USER y MAILSENDER_SERVICE_PASSWORD"
        )

    token = _get_service_token(identity_url, service_user, service_password)
    response = requests.post(
        f"{mailsender_url.rstrip('/')}/api/v1/emails",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    response.raise_for_status()


# =============================================================================
# Servicio de alertas de vencimientos
# =============================================================================

class AlertEmailService:
    """Envía emails de alertas de vencimiento SSN con throttle diario."""

    @staticmethod
    def already_sent_today() -> bool:
        try:
            return bool(caches["alerts"].get(_throttle_key()))
        except Exception:
            return False

    @staticmethod
    def _mark_sent_today():
        try:
            tomorrow = datetime.date.today() + datetime.timedelta(days=1)
            midnight = datetime.datetime.combine(tomorrow, datetime.time.min)
            ttl = int((midnight - datetime.datetime.now()).total_seconds()) + 60
            caches["alerts"].set(_throttle_key(), True, ttl)
        except Exception:
            logger.warning("ssn email: no se pudo registrar throttle", exc_info=True)

    @staticmethod
    def send_deadline_alerts(alerts: List[Alert], force: bool = False) -> bool:
        """
        Envía email con las alertas de vencimiento.

        Args:
            alerts: Lista de alertas a notificar.
            force:  Si True, ignora el throttle diario (--force en CLI).

        Returns:
            True si el email fue enviado, False si se omitió o falló.
        """
        if not alerts:
            logger.info("ssn email: no hay alertas para enviar")
            return False

        if not force and AlertEmailService.already_sent_today():
            logger.info("ssn email: ya enviado hoy, omitiendo")
            return False

        recipients = _get_recipients()
        if not recipients:
            logger.warning("ssn email: ALERT_EMAIL_RECIPIENTS no configurado")
            return False

        subject = _build_deadline_subject(alerts)

        try:
            mailsender_url = getattr(settings, "MAILSENDER_URL", "").strip()
            if mailsender_url:
                context = _build_deadline_context(alerts)
                html_body = render_to_string("emails/deadline_alerts.html", context)
                payload = _build_mailsender_payload(recipients, subject, html_body)
                _post_to_mailsender(payload, mailsender_url)
            else:
                _send_via_smtp(
                    recipients, subject,
                    "emails/deadline_alerts.html",
                    _build_deadline_context(alerts),
                )

            AlertEmailService._mark_sent_today()
            logger.info("ssn email alertas: enviado a %d destinatario(s)", len(recipients))
            return True

        except Exception:
            logger.exception("ssn email alertas: error al enviar")
            return False

    # Exponemos _get_recipients para que el management command pueda mostrar el count
    @staticmethod
    def _get_recipients() -> List[str]:
        return _get_recipients()


# =============================================================================
# Servicio de confirmación de presentación
# =============================================================================

class PresentacionEmailService:
    """Envía email de confirmación cuando una presentación es exitosa en SSN."""

    @staticmethod
    def send_confirmacion(base_request, operations, ssn_message: str = "") -> bool:
        """
        Envía email de confirmación de presentación SSN.

        Args:
            base_request: Instancia de BaseRequestModel ya en estado PRESENTADO/CARGADO.
            operations:   QuerySet/lista de operaciones incluidas.
            ssn_message:  Mensaje textual devuelto por la SSN (puede ser vacío).

        Returns:
            True si el email fue enviado, False si falló o no está configurado.
        """
        recipients = _get_recipients()
        if not recipients:
            logger.debug("ssn email presentación: sin destinatarios configurados")
            return False

        subject = _build_presentacion_subject(base_request)

        try:
            mailsender_url = getattr(settings, "MAILSENDER_URL", "").strip()
            context = _build_presentacion_context(base_request, operations, ssn_message)

            if mailsender_url:
                html_body = render_to_string("emails/presentacion_confirmacion.html", context)
                payload = _build_mailsender_payload(recipients, subject, html_body)
                _post_to_mailsender(payload, mailsender_url)
            else:
                _send_via_smtp(
                    recipients, subject,
                    "emails/presentacion_confirmacion.html",
                    context,
                )

            logger.info(
                "ssn email presentación: confirmación enviada [%s %s]",
                base_request.tipo_entrega,
                base_request.cronograma,
            )
            return True

        except Exception:
            logger.exception("ssn email presentación: error al enviar confirmación")
            return False


# =============================================================================
# Helpers compartidos (privados al módulo)
# =============================================================================

def _get_recipients() -> List[str]:
    raw = getattr(settings, "ALERT_EMAIL_RECIPIENTS", "")
    return [r.strip() for r in raw.split(",") if r.strip()]


def _build_mailsender_payload(recipients: List[str], subject: str, html_body: str) -> dict:
    """Arma el payload para POST /api/v1/emails de Mailsender."""
    payload: dict = {
        "to": [{"email": recipients[0], "name": ""}],
        "subject": subject,
        "html_content": html_body,
        "priority": "normal",
        "email_type": "ssn_notification",
    }
    if len(recipients) > 1:
        payload["bcc"] = [{"email": e, "name": ""} for e in recipients[1:]]
    return payload


def _send_via_smtp(
    recipients: List[str],
    subject: str,
    template: str,
    context: dict,
) -> None:
    html_message = render_to_string(template, context)
    plain_message = strip_tags(html_message)
    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipients,
        html_message=html_message,
        fail_silently=False,
    )


# --- Alertas de vencimiento ---

def _build_deadline_subject(alerts: List[Alert]) -> str:
    criticas = sum(1 for a in alerts if a.level == AlertLevel.DANGER)
    if criticas > 0:
        return f"[SSN] URGENTE: {criticas} presentación(es) vencida(s)"
    return f"[SSN] Recordatorio: {len(alerts)} presentación(es) pendiente(s)"


def _build_deadline_context(alerts: List[Alert]) -> dict:
    return {
        "alertas": alerts,
        "total_alertas": len(alerts),
        "alertas_criticas": sum(1 for a in alerts if a.level == AlertLevel.DANGER),
        "alertas_warning": sum(1 for a in alerts if a.level == AlertLevel.WARNING),
        "company_name": getattr(settings, "COMPANY_NAME", "Sistema SSN"),
        "base_url": getattr(settings, "BASE_URL", "").rstrip("/"),
    }


# --- Confirmación de presentación ---

def _build_presentacion_subject(base_request) -> str:
    tipo = base_request.tipo_entrega
    cronograma = base_request.cronograma
    return f"[SSN] Presentación {tipo} {cronograma} confirmada"


def _build_presentacion_context(base_request, operations, ssn_message: str) -> dict:
    ops_list = list(operations) if operations else []

    # Agrupar por tipo de operación si tienen ese campo
    tipos_op = {}
    for op in ops_list:
        tipo = getattr(op, "tipo_operacion", None) or getattr(op, "tipo", "Operación")
        tipo_label = str(tipo.label if hasattr(tipo, "label") else tipo)
        tipos_op[tipo_label] = tipos_op.get(tipo_label, 0) + 1

    base_url = getattr(settings, "BASE_URL", "").rstrip("/")
    from django.urls import reverse
    try:
        url_solicitud = f"{base_url}{reverse('operaciones:solicitud_respuesta', kwargs={'uuid': str(base_request.uuid)})}"
    except Exception:
        url_solicitud = ""

    return {
        "solicitud": base_request,
        "tipo_entrega": base_request.tipo_entrega,
        "cronograma": base_request.cronograma,
        "estado": base_request.estado,
        "total_operaciones": len(ops_list),
        "tipos_operacion": tipos_op,
        "ssn_message": ssn_message,
        "url_solicitud": url_solicitud,
        "company_name": getattr(settings, "COMPANY_NAME", "Sistema SSN"),
        "base_url": base_url,
    }
