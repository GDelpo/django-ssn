"""
Mixin para campos de timestamps reutilizables.
"""

from django.db import models


class TimestampMixin(models.Model):
    """
    Mixin abstracto que agrega campos created_at y updated_at a cualquier modelo.
    """

    created_at = models.DateTimeField(
        auto_now_add=True,
        null=True,
        blank=True,
        verbose_name="Fecha de Creación",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        null=True,
        blank=True,
        verbose_name="Última Modificación",
    )

    class Meta:
        abstract = True
