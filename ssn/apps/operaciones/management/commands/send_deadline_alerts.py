"""
Comando para enviar alertas de vencimientos SSN por email.

Refresca la caché de alertas (fuente única) y delega el envío en AlertEmailService.
Diseñado para ejecutarse como tarea programada (cron).

Uso:
    python manage.py send_deadline_alerts
    python manage.py send_deadline_alerts --dry-run
    python manage.py send_deadline_alerts --force     # ignora throttle diario
    python manage.py send_deadline_alerts --level danger

Ejemplo de cron diario a las 8:00 AM:
    0 8 * * * docker exec reports_web python ssn/manage.py send_deadline_alerts
"""

import logging

from django.core.management.base import BaseCommand

from operaciones.services.alert_service import AlertLevel, AlertService
from operaciones.services.email_service import AlertEmailService

logger = logging.getLogger("operaciones")

_LEVEL_ICONS = {
    AlertLevel.DANGER: "DANGER",
    AlertLevel.WARNING: "WARNING",
    AlertLevel.INFO: "INFO",
    AlertLevel.SUCCESS: "OK",
}


class Command(BaseCommand):
    help = "Envía alertas de vencimientos SSN pendientes por email"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra las alertas sin enviar emails",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Envía aunque ya se haya enviado hoy (ignora throttle)",
        )
        parser.add_argument(
            "--level",
            choices=["all", "danger", "warning"],
            default="warning",
            help="Nivel mínimo de alerta a enviar (default: warning)",
        )

    def handle(self, *args, **options):
        self.stdout.write("Verificando alertas de vencimientos SSN...")

        # Refresca la caché desde DB y obtiene alertas frescas
        alertas = AlertService.refresh_alerts()

        if not alertas:
            self.stdout.write(self.style.SUCCESS("No hay alertas pendientes"))
            return

        # Filtrar por nivel mínimo
        level_filter = options["level"]
        if level_filter == "danger":
            alertas = [a for a in alertas if a.level == AlertLevel.DANGER]
        elif level_filter == "warning":
            alertas = [a for a in alertas if a.level in (AlertLevel.DANGER, AlertLevel.WARNING)]

        if not alertas:
            self.stdout.write(self.style.SUCCESS("No hay alertas del nivel especificado"))
            return

        # Mostrar resumen
        self.stdout.write(f"\nAlertas encontradas: {len(alertas)}")
        for alerta in alertas:
            icon = _LEVEL_ICONS.get(alerta.level, "?")
            self.stdout.write(f"  [{icon}] {alerta.title}: {alerta.message}")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("\nModo dry-run: no se enviaron emails"))
            return

        # Enviar via AlertEmailService (dual-mode SMTP / Mailsender)
        sent = AlertEmailService.send_deadline_alerts(
            alertas,
            force=options["force"],
        )

        if sent:
            recipients = AlertEmailService._get_recipients()
            self.stdout.write(
                self.style.SUCCESS(f"\nEmail enviado a {len(recipients)} destinatario(s)")
            )
        elif AlertEmailService.already_sent_today() and not options["force"]:
            self.stdout.write(
                self.style.WARNING(
                    "\nEmail ya enviado hoy. Usar --force para reenviar."
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR("\nNo se pudo enviar el email (ver logs para detalles)")
            )
