"""
Modelo de operación de Compra semanal.
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


class CompraOperacion(
    BaseOperacionModel,
    EspecieOperacionMixin,
    AfectacionMixin,
    CantidadEspeciesMixin,
    ComprobanteMixin,
):
    """
    Operación de compra de especies (semanal).
    """

    precio_compra = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text="Precio de compra",
    )
    solicitud = models.ForeignKey(
        "operaciones.BaseRequestModel",
        on_delete=models.CASCADE,
        related_name="compras",
        null=True,
        blank=True,
        help_text="Solicitud a la que pertenece esta compra",
    )

    def clean(self):
        super().clean()
        errors = {}

        if self.precio_compra <= 0:
            errors["precio_compra"] = "El precio de compra debe ser mayor a cero."

        if self.fecha_liquidacion < self.fecha_movimiento:
            errors["fecha_liquidacion"] = (
                "La fecha de liquidación no puede ser anterior a la de movimiento."
            )

        if self.cant_especies <= 0:
            errors["cant_especies"] = "La cantidad de especies debe ser mayor a cero."

        # Validar cantidad según tipo de especie
        self._validate_cantidad_especies()

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Redondear a entero si no es FCI
        if self.cant_especies is not None:
            if self.tipo_especie != TipoEspecie.FONDOS_COMUNES_DE_INVERSIÓN:
                self.cant_especies = int(self.cant_especies)
        super().save(*args, **kwargs)

    def __str__(self):
        from ...helpers.text_utils import format_ar_number
        return f"Compra: {self.codigo_especie} x {format_ar_number(self.cant_especies)}"

    class Meta:
        app_label = 'operaciones'
        verbose_name = "Compra"
        verbose_name_plural = "Compras"
        db_table = "db_compras_operacion"
