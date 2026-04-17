"""
Stock de Cheque Pago Diferido mensual.
"""

from django.db import models

from ..base import BaseMonthlyStock
from ..choices import TipoStock, TipoTasa


class ChequePagoDiferidoStock(BaseMonthlyStock):
    """
    Stock de tipo Cheque Pago Diferido para entrega mensual.
    Hereda afectación, timestamps y datos comunes de stock.
    """

    tipo = models.CharField(
        max_length=1,
        choices=TipoStock.choices,
        default=TipoStock.CHEQUE_PD,
        help_text="Tipo de stock (C=Cheque PD)",
    )

    # Campos de moneda y tasa (similares a PlazoFijo pero no hereda todo)
    moneda = models.CharField(
        max_length=3,
        help_text="Código de moneda",
    )
    tipo_tasa = models.CharField(
        max_length=1,
        choices=TipoTasa.choices,
        help_text="F si es Fija, V si es Variable",
    )
    tasa = models.DecimalField(
        max_digits=5,
        decimal_places=3,
        help_text="Tasa aplicada",
    )

    # Campos específicos de Cheque PD
    codigo_sgr = models.CharField(
        max_length=3,
        help_text="Código SGR",
    )
    codigo_cheque = models.CharField(
        max_length=16,
        help_text="Código del cheque",
    )
    fecha_emision = models.DateField(
        help_text="Fecha de emisión (DDMMYYYY)",
    )
    fecha_vencimiento = models.DateField(
        help_text="Fecha de vencimiento (DDMMYYYY)",
    )
    valor_nominal = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        help_text="Valor nominal del cheque",
    )
    valor_adquisicion = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        help_text="Valor de adquisición del cheque",
    )
    grupo_economico = models.BooleanField(
        default=False,
        help_text="Emisor pertenece a grupo económico (1: Sí, 0: No)",
    )
    fecha_adquisicion = models.DateField(
        help_text="Fecha de adquisición (DDMMYYYY)",
    )

    solicitud = models.ForeignKey(
        "operaciones.BaseRequestModel",
        on_delete=models.CASCADE,
        related_name="stocks_chequespd_mensuales",
        help_text="Solicitud mensual a la que pertenece este stock",
    )

    @property
    def tipo_operacion(self):
        """Tipo de operación para compatibilidad con templates."""
        return "SC"  # Stock Cheque PD

    def get_tipo_operacion_display(self):
        """Display del tipo de operación."""
        return "Cheque P.D."

    def __str__(self):
        return f"Cheque {self.codigo_cheque} @ {self.solicitud.cronograma}"

    class Meta:
        app_label = 'operaciones'
        verbose_name = "Stock Cheque Pago Diferido Mensual"
        verbose_name_plural = "Stocks Cheque Pago Diferido Mensuales"
        ordering = ["-solicitud", "codigo_cheque"]
