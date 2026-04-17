"""
Stock de Inversión mensual.
"""

from django.core.exceptions import ValidationError
from django.db import models

from ..base import BaseMonthlyStock, EspecieOperacionMixin, GrupoEconomicoMixin
from ..choices import TipoEspecie, TipoStock


class InversionStock(
    BaseMonthlyStock,
    EspecieOperacionMixin,
    GrupoEconomicoMixin,
):
    """
    Stock de tipo Inversión para entrega mensual.
    Hereda especie, afectación, timestamps y datos de grupo económico.
    """

    tipo = models.CharField(
        max_length=1,
        choices=TipoStock.choices,
        default=TipoStock.INVERSION,
        help_text="Tipo de stock (I=Inversión)",
    )

    cantidad_devengado_especies = models.DecimalField(
        max_digits=20,
        decimal_places=6,
        help_text="Cantidad devengada de especies",
    )
    cantidad_percibido_especies = models.DecimalField(
        max_digits=20,
        decimal_places=6,
        help_text="Cantidad percibida de especies",
    )
    con_cotizacion = models.BooleanField(
        default=True,
        help_text="Indicador de cotización (1: Sí, 0: No)",
    )
    emisor_art_ret = models.BooleanField(
        default=False,
        help_text="Emisor ART/RET (1: Sí, 0: No)",
    )
    prevision_desvalorizacion = models.DecimalField(
        max_digits=14,
        decimal_places=0,
        blank=True,
        null=True,
        help_text="Previsión desvalorización",
    )
    fecha_pase_vt = models.DateField(
        blank=True,
        null=True,
        help_text="Fecha de pase a VT (DDMMYYYY)",
    )
    precio_pase_vt = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Precio de pase a VT",
    )
    valor_financiero = models.DecimalField(
        max_digits=14,
        decimal_places=0,
        blank=True,
        null=True,
        help_text="Valor financiero",
    )

    solicitud = models.ForeignKey(
        "operaciones.BaseRequestModel",
        on_delete=models.CASCADE,
        related_name="stocks_inversion_mensuales",
        help_text="Solicitud mensual a la que pertenece este stock",
    )

    def clean(self):
        """Valida que las cantidades sean enteras excepto para FCI."""
        super().clean()
        errors = {}
        
        # Solo FCI puede tener decimales en cantidades
        is_fci = self.tipo_especie == TipoEspecie.FONDOS_COMUNES_DE_INVERSIÓN
        
        if not is_fci:
            if self.cantidad_devengado_especies is not None:
                if self.cantidad_devengado_especies % 1 != 0:
                    errors["cantidad_devengado_especies"] = (
                        "Para este tipo de especie, la cantidad debe ser un número entero."
                    )
            
            if self.cantidad_percibido_especies is not None:
                if self.cantidad_percibido_especies % 1 != 0:
                    errors["cantidad_percibido_especies"] = (
                        "Para este tipo de especie, la cantidad debe ser un número entero."
                    )
        
        if errors:
            raise ValidationError(errors)

    @property
    def tipo_operacion(self):
        """Tipo de operación para compatibilidad con templates."""
        return "SI"  # Stock Inversión

    def get_tipo_operacion_display(self):
        """Display del tipo de operación."""
        return "Inversión"

    def __str__(self):
        return f"{self.tipo_especie} - {self.codigo_especie}"

    class Meta:
        app_label = 'operaciones'
        verbose_name = "Stock Inversión Mensual"
        verbose_name_plural = "Stocks Inversión Mensuales"
        ordering = ["-solicitud", "codigo_especie"]
