from django import forms as django_forms
from django import template

from operaciones.helpers.text_utils import format_ar_number

register = template.Library()


@register.filter
def ar_decimal(value):
    """Formatea un número con separadores argentinos (punto miles, coma decimal)."""
    return format_ar_number(value)


@register.filter
def is_numeric_field(bound_field):
    """True si el campo del formulario es numérico (Decimal, Float, Integer)."""
    return isinstance(
        bound_field.field,
        (django_forms.DecimalField, django_forms.FloatField, django_forms.IntegerField),
    )


@register.inclusion_tag("componentes/link_button.html")
def link_button(href, label=None, icon=None, color="secondary", size="md", id=None):
    """
    Prepara un contexto seguro y completo para el componente de botón.
    Acepta argumentos por palabra clave y establece valores por defecto.
    """
    return {
        "href": href,
        "label": label,
        "icon": icon,
        "color": color,
        "size": size,
        "id": id,
    }
