import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation


def normalizar_texto(texto: str) -> str:
    """Elimina acentos/diacríticos y convierte a minúsculas para comparación robusta.

    Args:
        texto (str): Texto con posibles acentos o mayúsculas.

    Returns:
        str: Texto normalizado sin acentos, en minúsculas y sin espacios extra.

    Example:
        >>> normalizar_texto("VACÍO")
        'vacio'
        >>> normalizar_texto("Rectificación Pendiente")
        'rectificacion pendiente'
    """
    nfkd = unicodedata.normalize("NFKD", texto)
    sin_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sin_acentos.strip().lower()


def camel_to_title(text):
    """
    Convierte un texto en formato camelCase a Title Case.

    Args:
        text (str): Texto en formato camelCase.

    Returns:
        str: Texto formateado en Title Case.

    Example:
        >>> camel_to_title("nombreUsuario")
        'Nombre Usuario'
    """
    return re.sub(r"(?<!^)(?=[A-Z])", " ", text).title()


def to_camel_case(snake_str):
    """
    Convierte un string en formato snake_case a camelCase.
    """
    components = snake_str.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def format_ar_number(value) -> str:
    """
    Formatea un número con separadores argentinos: punto para miles, coma para decimal.
    Elimina ceros decimales trailing.

    Ejemplos:
        1234567.890100  →  "1.234.567,8901"
        12345.67        →  "12.345,67"
        100000.00       →  "100.000"
        250.75          →  "250,75"
        321             →  "321"
    """
    if value is None:
        return ""
    try:
        d = Decimal(str(value)).normalize()
        # format(d, 'f') evita notación científica en números grandes/pequeños
        str_d = format(d, "f")
        if "." in str_d:
            int_part, dec_part = str_d.split(".")
            dec_part = dec_part.rstrip("0")
        else:
            int_part = str_d
            dec_part = ""

        negative = int_part.startswith("-")
        abs_int = int_part.lstrip("-")
        int_formatted = "{:,}".format(int(abs_int)).replace(",", ".")
        if negative:
            int_formatted = "-" + int_formatted

        return f"{int_formatted},{dec_part}" if dec_part else int_formatted
    except (InvalidOperation, ValueError):
        return str(value)


def pretty_json(data):
    """
    Converts a Python object into a formatted JSON string with indentation for readability.
    Args:
        data (Any): The Python object to be serialized into JSON.
    Returns:
        str: A JSON-formatted string representation of the input data, indented for readability and preserving non-ASCII characters.
    """

    return json.dumps(data, indent=4, ensure_ascii=False)
