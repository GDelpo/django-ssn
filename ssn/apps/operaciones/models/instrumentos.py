
from django.db import models
from .choices import TipoEspecie, TipoTasa

class Especie(models.Model):
    """
    Modelo Maestro para Títulos, ONs, FCIs, etc.
    Representa una única especie negociable.
    """
    tipo_especie = models.CharField(
        max_length=2,
        choices=TipoEspecie.choices,
        help_text="Tipo de especie (TP, ON, FC, etc.)",
    )
    codigo_especie = models.CharField(
        max_length=20, 
        help_text="Código SSN único de la especie",
        db_index=True
    )

    class Meta:
        verbose_name = "Instrumento - Especie"
        verbose_name_plural = "Instrumentos - Especies"
        db_table = "db_instrumento_especie"
        ordering = ['tipo_especie', 'codigo_especie']
        constraints = [
            models.UniqueConstraint(fields=['tipo_especie', 'codigo_especie'], name='unique_instrumento_especie')
        ]

    def __str__(self):
        return f"{self.get_tipo_especie_display()} ({self.codigo_especie})"
    
class PlazoFijoInstrumento(models.Model):
    """
    Modelo Maestro para Plazos Fijos.
    Representa una única instancia de constitución de un Plazo Fijo.
    """
    cdf = models.CharField(
        max_length=20, 
        unique=True, 
        help_text="Código CDF (Certificado del Depósito a Plazo Fijo)"
    )
    bic = models.CharField(max_length=12, help_text="Código BIC (Bancos)")
    tipo_pf = models.CharField(max_length=3, help_text="Tipo de depósito")
    moneda = models.CharField(max_length=3, help_text="Código de moneda")
    tipo_tasa = models.CharField(max_length=1, choices=TipoTasa.choices)
    tasa = models.DecimalField(max_digits=5, decimal_places=3)
    titulo_deuda = models.BooleanField()
    codigo_titulo = models.CharField(max_length=3, blank=True, null=True)
    
    class Meta:
        verbose_name = "Instrumento - Plazo Fijo"
        verbose_name_plural = "Instrumentos - Plazos Fijos"
        db_table = "db_instrumento_plazo_fijo"
        ordering = ['-cdf']

    def __str__(self):
        return f"PF {self.cdf} ({self.bic})"
