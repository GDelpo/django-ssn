"""
Clases base abstractas para operaciones semanales y stocks mensuales.
Proporciona mixins reutilizables con atributos comunes.
"""

from django.db import models

from ..choices import TipoEspecie, TipoOperacion, TipoTasa, TipoValuacion
from .timestamps import TimestampMixin

# Funciones para validación de archivos - definidas inline para evitar circular import
import datetime
import os

import magic
from django.conf import settings
from django.forms import ValidationError
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


def _validate_file_extension(value):
    """Valida que la extensión del archivo subido esté permitida."""
    ext = os.path.splitext(value.name)[1].lower()
    allowed_extensions = getattr(
        settings, "ALLOWED_UPLOAD_EXTENSIONS", [".pdf", ".png", ".jpg", ".jpeg"]
    )
    if ext not in allowed_extensions:
        raise ValidationError(
            _("Formato de archivo no permitido. Los formatos permitidos son: %s.")
            % ", ".join(allowed_extensions)
        )


def _validate_file_size(value):
    """Valida que el tamaño del archivo no exceda el límite permitido."""
    max_size = getattr(settings, "MAX_UPLOAD_SIZE", 5 * 1024 * 1024)
    if value.size > max_size:
        raise ValidationError(
            _("El archivo es demasiado grande. El tamaño máximo permitido es %s MB.")
            % (max_size / (1024 * 1024))
        )


def _validate_file_content_type(value):
    """Valida que el tipo de contenido real del archivo coincida con la extensión."""
    mime_types = {
        ".pdf": ["application/pdf"],
        ".png": ["image/png"],
        ".jpg": ["image/jpeg"],
        ".jpeg": ["image/jpeg"],
    }
    ext = os.path.splitext(value.name)[1].lower()
    allowed_mime_types = mime_types.get(ext, [])
    if not allowed_mime_types:
        return
    try:
        file_mime = magic.from_buffer(value.read(1024), mime=True)
        if hasattr(value, "seek") and callable(value.seek):
            value.seek(0)
    except Exception:
        return
    if file_mime not in allowed_mime_types:
        raise ValidationError(
            _("El contenido del archivo no coincide con su extensión declarada.")
        )


def validate_comprobante_file(value):
    """Función completa para validar archivos de comprobante."""
    _validate_file_extension(value)
    _validate_file_size(value)
    _validate_file_content_type(value)


def comprobante_upload_path(instance, filename):
    """Retorna el path de almacenamiento para el comprobante."""
    base, ext = os.path.splitext(filename)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%Mhs")
    tipo_operacion = instance.get_tipo_operacion_display()
    tipo_operacion_slug = slugify(tipo_operacion)
    slug = slugify(base)[:40]
    max_slug_length = 100 - len(tipo_operacion_slug) - len(timestamp) - len(ext) - 2
    slug = slug[:max_slug_length]
    new_filename = f"{tipo_operacion_slug}_{slug}_{timestamp}{ext}"
    solicitud_uuid = getattr(instance.solicitud, "uuid", "sin_solicitud")
    return os.path.join("comprobantes", str(solicitud_uuid), new_filename)


# =============================================================================
# MIXINS BÁSICOS (Atributos atómicos reutilizables)
# =============================================================================


class AfectacionMixin(models.Model):
    """
    Mixin con código de afectación.
    Usado tanto en operaciones semanales como en stocks mensuales.
    """

    codigo_afectacion = models.CharField(
        max_length=3,
        help_text="Código de afectación",
    )

    class Meta:
        abstract = True


class EspecieOperacionMixin(models.Model):
    """
    Mixin con datos de especie financiera.
    Común para operaciones de compra/venta e inversiones mensuales.
    """

    tipo_especie = models.CharField(
        max_length=2,
        choices=TipoEspecie.choices,
        help_text="Tipo de especie (TP, ON, FC, etc.)",
    )
    codigo_especie = models.CharField(
        max_length=20,
        help_text="Código SSN de la especie",
    )
    tipo_valuacion = models.CharField(
        max_length=1,
        choices=TipoValuacion.choices,
        help_text="Tipo de valuación (T → Técnico | V → Mercado)",
    )

    class Meta:
        abstract = True


class CantidadEspeciesMixin(models.Model):
    """
    Mixin para cantidad de especies con validación según tipo.
    """

    cant_especies = models.DecimalField(
        max_digits=20,
        decimal_places=6,
        help_text="Cantidad de especies (valor nominal)",
    )

    def _validate_cantidad_especies(self):
        """Valida que FCI pueda tener decimales y otras especies no."""
        if hasattr(self, "cant_especies") and self.cant_especies is not None:
            decimal_part = self.cant_especies % 1
            if (
                hasattr(self, "tipo_especie")
                and self.tipo_especie != TipoEspecie.FONDOS_COMUNES_DE_INVERSIÓN
                and decimal_part != 0
            ):
                from django.core.exceptions import ValidationError

                raise ValidationError(
                    {
                        "cant_especies": "Para este tipo de especie, la cantidad debe ser un número entero."
                    }
                )

    class Meta:
        abstract = True


class ComprobanteMixin(models.Model):
    """
    Mixin para adjuntar comprobante.
    """

    comprobante = models.FileField(
        upload_to=comprobante_upload_path,
        validators=[validate_comprobante_file],
        null=True,
        blank=True,
        help_text="Adjunta el comprobante (PDF, imagen, etc.)",
    )

    class Meta:
        abstract = True


class PlazoFijoBaseMixin(models.Model):
    """
    Mixin con campos comunes para Plazo Fijo (semanal y mensual).
    """

    tipo_pf = models.CharField(
        max_length=3,
        help_text="Código de Tipo de Depósito",
    )
    bic = models.CharField(
        max_length=12,
        help_text="Código BIC del banco",
    )
    cdf = models.CharField(
        max_length=20,
        help_text="Certificado del Depósito a Plazo",
    )
    fecha_constitucion = models.DateField(
        help_text="Fecha de constitución (DDMMYYYY)",
    )
    fecha_vencimiento = models.DateField(
        help_text="Fecha de vencimiento (DDMMYYYY)",
    )
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
    titulo_deuda = models.BooleanField(
        default=False,
        help_text="Indica si está relacionado con un título de deuda pública",
    )
    codigo_titulo = models.CharField(
        max_length=3,
        blank=True,
        null=True,
        help_text="Código de título público",
    )

    class Meta:
        abstract = True


class ValorNominalMixin(models.Model):
    """
    Mixin para valores nominales (origen y nacional).
    """

    valor_nominal_origen = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        blank=True,
        null=True,
        help_text="Valor nominal en moneda origen (vacío si es ARS)",
    )
    valor_nominal_nacional = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        help_text="Valor nominal en Pesos Argentinos",
    )

    class Meta:
        abstract = True


class GrupoEconomicoMixin(models.Model):
    """
    Mixin para indicador de grupo económico.
    """

    emisor_grupo_economico = models.BooleanField(
        default=False,
        help_text="Emisor pertenece a grupo económico (1: Sí, 0: No)",
    )

    class Meta:
        abstract = True


# =============================================================================
# CLASES BASE PARA OPERACIONES
# =============================================================================


class BaseOperacionModel(TimestampMixin):
    """
    Clase base abstracta para operaciones semanales.
    Incluye tipo de operación y fechas de movimiento/liquidación.
    """

    tipo_operacion = models.CharField(
        max_length=1,
        choices=TipoOperacion.choices,
        help_text="Tipo de operación a realizar",
    )
    fecha_movimiento = models.DateField(
        help_text="Fecha de movimiento (DDMMYYYY)",
    )
    fecha_liquidacion = models.DateField(
        help_text="Fecha de liquidación (DDMMYYYY)",
    )

    @property
    def fecha_operacion(self):
        """Alias para fecha_movimiento."""
        return self.fecha_movimiento

    class Meta:
        abstract = True


# =============================================================================
# CLASES BASE PARA STOCKS MENSUALES
# =============================================================================


class BaseMonthlyStock(TimestampMixin, AfectacionMixin):
    """
    Clase base abstracta para todos los stocks de entrega mensual.
    Hereda timestamps y código de afectación.
    """

    libre_disponibilidad = models.BooleanField(
        default=True,
        help_text="Libre disponibilidad (1: Sí, 0: No)",
    )
    en_custodia = models.BooleanField(
        default=True,
        help_text="Indicador en custodia (1: Sí, 0: No)",
    )
    financiera = models.BooleanField(
        default=True,
        help_text="Indicador financiera",
    )
    valor_contable = models.DecimalField(
        max_digits=14,
        decimal_places=0,
        help_text="Valor contable",
    )

    class Meta:
        abstract = True
