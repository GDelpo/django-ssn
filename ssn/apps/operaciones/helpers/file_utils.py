import datetime
import os

import magic
from django.conf import settings
from django.forms import ValidationError
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


def validate_file_extension(value):
    """
    Valida que la extensión del archivo subido esté permitida.

    Args:
        value: Archivo subido a validar

    Raises:
        ValidationError: Si la extensión no está permitida
    """
    ext = os.path.splitext(value.name)[1].lower()
    allowed_extensions = getattr(
        settings, "ALLOWED_UPLOAD_EXTENSIONS", [".pdf", ".png", ".jpg", ".jpeg"]
    )

    if ext not in allowed_extensions:
        raise ValidationError(
            _("Formato de archivo no permitido. Los formatos permitidos son: %s.")
            % ", ".join(allowed_extensions)
        )


def validate_file_size(value):
    """
    Valida que el tamaño del archivo no exceda el límite permitido.

    Args:
        value: Archivo subido a validar

    Raises:
        ValidationError: Si el archivo es demasiado grande
    """
    max_size = getattr(settings, "MAX_UPLOAD_SIZE", 5 * 1024 * 1024)  # 5MB por defecto
    if value.size > max_size:
        raise ValidationError(
            _("El archivo es demasiado grande. El tamaño máximo permitido es %s MB.")
            % (max_size / (1024 * 1024))
        )


def validate_file_content_type(value):
    """
    Valida que el tipo de contenido real del archivo coincida con la extensión.
    Esto ayuda a prevenir ataques donde un archivo malicioso se camufla con una extensión segura.

    Requiere la biblioteca python-magic.

    Args:
        value: Archivo subido a validar

    Raises:
        ValidationError: Si el tipo de contenido no coincide con la extensión
    """
    # Mapeo de extensiones a tipos MIME
    mime_types = {
        ".pdf": ["application/pdf"],
        ".png": ["image/png"],
        ".jpg": ["image/jpeg"],
        ".jpeg": ["image/jpeg"],
    }

    ext = os.path.splitext(value.name)[1].lower()
    allowed_mime_types = mime_types.get(ext, [])

    if not allowed_mime_types:
        return  # Si no hay tipo MIME definido para esta extensión, saltamos esta validación

    # Usar python-magic para determinar el tipo real
    try:
        file_mime = magic.from_buffer(value.read(1024), mime=True)
        # Importante: volver al inicio del archivo después de leerlo
        if hasattr(value, "seek") and callable(value.seek):
            value.seek(0)
    except Exception as e:
        # Si hay un error al leer el archivo, registrarlo y continuar
        import logging

        logger = logging.getLogger("operaciones")
        logger.warning(f"Error al validar tipo MIME: {e}")
        return

    if file_mime not in allowed_mime_types:
        raise ValidationError(
            _("El contenido del archivo no coincide con su extensión declarada.")
        )


def validate_comprobante_file(value):
    """
    Función completa para validar archivos de comprobante.
    Combina todas las validaciones anteriores.

    Args:
        value: Archivo a validar

    Raises:
        ValidationError: Si el archivo no cumple con los requisitos
    """
    validate_file_extension(value)
    validate_file_size(value)
    validate_file_content_type(value)


def comprobante_upload_path(instance, filename):
    """
    Retorna el path de almacenamiento para el comprobante.
    Se organiza en una carpeta 'comprobantes/<uuid_solicitud>/' y
    se formatea el nombre para incluir el tipo de operación legible, fecha y un slug del nombre original.

    Args:
        instance (Model): Instancia del modelo al que pertenece el archivo.
        filename (str): Nombre original del archivo subido.

    Returns:
        str: Ruta donde se almacenará el archivo.
    """
    base, ext = os.path.splitext(filename)
    timestamp = datetime.datetime.now().strftime(
        "%Y-%m-%d_%H-%Mhs"
    )  # Formato de fecha y hora

    # Obtiene la etiqueta legible del tipo de operación
    tipo_operacion = instance.get_tipo_operacion_display()
    tipo_operacion_slug = slugify(tipo_operacion)  # e.g. "compra", "venta"

    slug = slugify(base)[:40]

    # Asegura que el nombre completo no supere los 100 caracteres
    max_slug_length = 100 - len(tipo_operacion_slug) - len(timestamp) - len(ext) - 2
    slug = slug[:max_slug_length]

    new_filename = f"{tipo_operacion_slug}_{slug}_{timestamp}{ext}"

    solicitud_uuid = getattr(instance.solicitud, "uuid", "sin_solicitud")

    return os.path.join("comprobantes", str(solicitud_uuid), new_filename)
