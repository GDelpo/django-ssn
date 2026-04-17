"""
Modelo de solicitud base (BaseRequestModel).
"""

import uuid

from django.core.validators import MinLengthValidator
from django.db import models

from ..choices import EstadoSolicitud, TipoEntrega


class BaseRequestModel(models.Model):
    """
    Modelo base que representa una solicitud de entrega a la SSN.
    Puede ser semanal (operaciones) o mensual (stocks).
    """

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo_compania = models.CharField(
        max_length=4,
        validators=[MinLengthValidator(4)],
        help_text="Código identificador de la compañía (4 caracteres)",
    )
    tipo_entrega = models.CharField(
        max_length=10,
        choices=TipoEntrega.choices,
        help_text="Tipo de entrega (semanal o mensual)",
    )
    cronograma = models.CharField(
        max_length=7,
        validators=[MinLengthValidator(7)],
        help_text="Periodo del cronograma (YYYY-WW o YYYY-MM)",
    )

    estado = models.CharField(
        max_length=32,
        choices=EstadoSolicitud.choices,
        default=EstadoSolicitud.BORRADOR,
        help_text="Estado de la solicitud",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    send_at = models.DateTimeField(null=True, blank=True)

    @property
    def is_editable(self):
        """
        Determina si la solicitud puede ser editada.
        
        Estados editables:
        - BORRADOR: Creado localmente, aún no enviado
        - CARGADO: Enviado a SSN sin confirmar
        - A_RECTIFICAR: SSN aprobó la rectificación
        """
        return self.estado in [
            EstadoSolicitud.BORRADOR,
            EstadoSolicitud.CARGADO,
            EstadoSolicitud.A_RECTIFICAR,
        ]

    def sync_estado_con_ssn(self):
        """
        Sincroniza el estado local con el estado en la SSN.
        Retorna True si hubo cambio de estado, False en caso contrario.

        Regla de no-regresión: si el estado local es RECTIFICACION_PENDIENTE y la SSN
        todavía devuelve PRESENTADO, significa que la SSN aún no procesó la solicitud
        de rectificación. En ese caso NO se sobreescribe el estado local.
        """
        if self.estado == EstadoSolicitud.BORRADOR:
            return False

        from ssn_client.services import consultar_estado_ssn, EstadoSSN
        import logging

        logger = logging.getLogger("operaciones")
        estado_ssn, _, status = consultar_estado_ssn(self)

        if status < 400 and estado_ssn:
            estado_local_mapping = {
                EstadoSSN.VACIO: EstadoSolicitud.BORRADOR,
                EstadoSSN.CARGADO: EstadoSolicitud.CARGADO,
                EstadoSSN.PRESENTADO: EstadoSolicitud.PRESENTADO,
                EstadoSSN.RECTIFICACION_PENDIENTE: EstadoSolicitud.RECTIFICACION_PENDIENTE,
                EstadoSSN.A_RECTIFICAR: EstadoSolicitud.A_RECTIFICAR,
            }

            nuevo_estado = estado_local_mapping.get(estado_ssn)

            # Protección: no revertir RECTIFICACION_PENDIENTE a PRESENTADO.
            # Ocurre inmediatamente después de solicitar la rectificación,
            # cuando la SSN aún no reflejó el cambio.
            if (
                self.estado == EstadoSolicitud.RECTIFICACION_PENDIENTE
                and nuevo_estado == EstadoSolicitud.PRESENTADO
            ):
                logger.info(
                    f"Sync omitida para {self.uuid}: estado local RECTIFICACION_PENDIENTE "
                    f"conservado (SSN aún reporta PRESENTADO)."
                )
                return False

            if nuevo_estado and nuevo_estado != self.estado:
                logger.info(
                    f"Sincronizando estado de {self.uuid}: "
                    f"{self.estado} -> {nuevo_estado} (SSN: {estado_ssn})"
                )
                self.estado = nuevo_estado
                self.save()
                return True

        return False

    def __str__(self):
        return f"Tipo de Entrega: {self.tipo_entrega} | Cronograma: {self.cronograma}"

    class Meta:
        app_label = 'operaciones'
        verbose_name = "Solicitud Base"
        verbose_name_plural = "Solicitudes Base"
        db_table = "db_solicitudes_base"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tipo_entrega", "cronograma"],
                name="unique_entrega_cronograma",
            )
        ]
