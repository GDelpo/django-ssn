"""
Modelo de operación de Canje semanal.
"""

from django.core.exceptions import ValidationError
from django.db import models

from ..base import (
    BaseOperacionModel,
    EspecieOperacionMixin,
    AfectacionMixin,
    CantidadEspeciesMixin,
    ComprobanteMixin,
)
from ..choices import TipoEspecie


class DetalleOperacionCanje(
    EspecieOperacionMixin,
    AfectacionMixin,
    CantidadEspeciesMixin,
    ComprobanteMixin,
    models.Model,
):
    """
    Detalle de una operación de canje (parte A o B).
    """

    fecha_pase_vt = models.DateField(
        help_text="Fecha de pase a venta (DDMMYYYY)",
    )
    precio_pase_vt = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        help_text="Precio de pase a venta",
    )

    def clean(self):
        super().clean()
        # Validar cantidad según tipo de especie
        self._validate_cantidad_especies()

    def save(self, *args, **kwargs):
        # Redondear a entero si no es FCI
        if self.cant_especies is not None:
            if self.tipo_especie != TipoEspecie.FONDOS_COMUNES_DE_INVERSIÓN:
                self.cant_especies = int(self.cant_especies)
        super().save(*args, **kwargs)

    class Meta:
        app_label = 'operaciones'
        verbose_name = "Detalle de Canje"
        verbose_name_plural = "Detalles de Canje"


class CanjeOperacion(BaseOperacionModel):
    """
    Operación de canje de especies (semanal).
    Involucra dos detalles: A (entrega) y B (recibe).
    """

    detalle_a = models.OneToOneField(
        DetalleOperacionCanje,
        on_delete=models.CASCADE,
        related_name="canje_operacion_a",
        help_text="Datos de la operación A (entrega)",
    )
    detalle_b = models.OneToOneField(
        DetalleOperacionCanje,
        on_delete=models.CASCADE,
        related_name="canje_operacion_b",
        help_text="Datos de la operación B (recibe)",
    )
    solicitud = models.ForeignKey(
        "operaciones.BaseRequestModel",
        on_delete=models.CASCADE,
        related_name="canjes",
        null=True,
        blank=True,
        help_text="Solicitud a la que pertenece este canje",
    )

    def __str__(self):
        return f"Canje - {self.fecha_movimiento}"

    def clean(self):
        super().clean()
        errors = {}

        if not self.detalle_a or not self.detalle_b:
            errors["detalle_a"] = "Ambos detalles deben estar presentes."
            errors["detalle_b"] = "Ambos detalles deben estar presentes."

        if self.detalle_a == self.detalle_b:
            errors["detalle_b"] = "Los detalles A y B deben ser distintos."

        # Validación cruzada
        if (
            self.detalle_a
            and self.detalle_b
            and self.detalle_a.fecha_pase_vt > self.detalle_b.fecha_pase_vt
        ):
            errors["detalle_b"] = (
                "La fecha de pase VT de B no puede ser anterior a la de A."
            )

        if errors:
            raise ValidationError(errors)

    class Meta:
        app_label = 'operaciones'
        verbose_name = "Canje"
        verbose_name_plural = "Canjes"
        db_table = "db_canjes_operacion"
