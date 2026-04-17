"""
Modelo de operación de Plazo Fijo semanal.
"""

from django.core.exceptions import ValidationError
from django.db import models

from ..base import (
    TimestampMixin,
    AfectacionMixin,
    PlazoFijoBaseMixin,
    ValorNominalMixin,
    ComprobanteMixin,
)
from ..choices import TipoOperacion


class PlazoFijoOperacion(
    TimestampMixin,
    AfectacionMixin,
    PlazoFijoBaseMixin,
    ValorNominalMixin,
    ComprobanteMixin,
    models.Model,
):
    """
    Operación de Plazo Fijo (semanal).
    """

    tipo_operacion = models.CharField(
        max_length=1,
        choices=TipoOperacion.choices,
        help_text="Tipo de operación: Plazo Fijo",
    )
    solicitud = models.ForeignKey(
        "operaciones.BaseRequestModel",
        on_delete=models.CASCADE,
        related_name="plazos_fijos",
        null=True,
        blank=True,
        help_text="Solicitud a la que pertenece este plazo fijo",
    )

    def clean(self):
        super().clean()
        errors = {}

        if self.fecha_vencimiento <= self.fecha_constitucion:
            errors["fecha_vencimiento"] = (
                "La fecha de vencimiento debe ser posterior a la fecha de constitución."
            )

        if self.valor_nominal_origen and self.valor_nominal_origen <= 0:
            errors["valor_nominal_origen"] = (
                "El valor nominal de origen debe ser mayor a cero."
            )

        if self.valor_nominal_nacional <= 0:
            errors["valor_nominal_nacional"] = (
                "El valor nominal nacional debe ser mayor a cero."
            )

        if self.tasa < 0:
            errors["tasa"] = "La tasa no puede ser negativa."

        if self.titulo_deuda and not self.codigo_titulo:
            errors["codigo_titulo"] = (
                "Debe ingresar el código del Título de Deuda si corresponde."
            )

        if not self.titulo_deuda and self.codigo_titulo:
            errors["codigo_titulo"] = (
                "No debe ingresar código de Título de Deuda si no corresponde."
            )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"PF: {self.bic} - {self.cdf}"

    class Meta:
        app_label = 'operaciones'
        verbose_name = "Plazo Fijo (Operación)"
        verbose_name_plural = "Plazos Fijos (Operaciones)"
        db_table = "db_plazos_fijos_operacion"
