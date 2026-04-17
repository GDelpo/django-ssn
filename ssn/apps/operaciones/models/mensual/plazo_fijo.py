"""
Stock de Plazo Fijo mensual.
"""

from django.db import models

from ..base import (
    BaseMonthlyStock,
    PlazoFijoBaseMixin,
    ValorNominalMixin,
    GrupoEconomicoMixin,
)
from ..choices import TipoStock


class PlazoFijoStock(
    BaseMonthlyStock,
    PlazoFijoBaseMixin,
    ValorNominalMixin,
    GrupoEconomicoMixin,
):
    """
    Stock de tipo Plazo Fijo para entrega mensual.
    Hereda campos de plazo fijo, valores nominales, afectación y timestamps.
    """

    tipo = models.CharField(
        max_length=1,
        choices=TipoStock.choices,
        default=TipoStock.PLAZO_FIJO,
        help_text="Tipo de stock (P=Plazo Fijo)",
    )

    solicitud = models.ForeignKey(
        "operaciones.BaseRequestModel",
        on_delete=models.CASCADE,
        related_name="stocks_plazofijo_mensuales",
        help_text="Solicitud mensual a la que pertenece este stock",
    )

    @property
    def tipo_operacion(self):
        """Tipo de operación para compatibilidad con templates."""
        return "SP"  # Stock Plazo Fijo

    def get_tipo_operacion_display(self):
        """Display del tipo de operación."""
        return "Plazo Fijo"

    def __str__(self):
        return f"{self.bic} @ {self.solicitud.cronograma}"

    class Meta:
        app_label = 'operaciones'
        verbose_name = "Stock Plazo Fijo Mensual"
        verbose_name_plural = "Stocks Plazo Fijo Mensuales"
        ordering = ["-solicitud", "bic"]
