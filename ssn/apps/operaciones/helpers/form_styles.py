from django import forms

# Constantes base y estados
FOCUS_RING = "focus:ring-2 focus:ring-blue-500 focus:ring-opacity-20 focus:outline-none"
HOVER_STATE = "hover:border-blue-300"
TRANSITION = "transition-all duration-200"
BASE_SHAPE = "w-full rounded-md border-gray-300 shadow-sm"

# Clase base combinada
CLASS_BASE = f"{BASE_SHAPE} {FOCUS_RING} {HOVER_STATE} {TRANSITION}"

# Clases específicas por tipo
CLASS_SELECT = f"{CLASS_BASE} pr-10 appearance-none bg-no-repeat bg-right"
CLASS_INPUT = f"{CLASS_BASE}"
CLASS_DATE = f"{CLASS_INPUT} pl-3 pr-10"
CLASS_NUMBER = f"{CLASS_INPUT} pl-3 pr-10"
CLASS_TEXTAREA = f"{CLASS_BASE} resize-none"
CLASS_CHECKBOX = "rounded border-gray-300 text-blue-600 shadow-sm focus:border-blue-300 focus:ring focus:ring-blue-200 focus:ring-opacity-50 transition"
CLASS_RADIO = "rounded-full border-gray-300 text-blue-600 shadow-sm focus:border-blue-300 focus:ring focus:ring-blue-200 focus:ring-opacity-50 transition"

# Mejora para input de archivo con estilo personalizado
CLASS_FILE = f"{CLASS_BASE} bg-white cursor-pointer file:mr-4 file:py-2 file:px-4 file:border-0 file:font-semibold file:bg-blue-50 file:text-blue-700 file:transition file:duration-200 file:cursor-pointer file:hover:bg-blue-100"


def actualizar_widget_attrs(widget, placeholder=None, required=False):
    """
    Aplica estilos Tailwind al widget según su tipo.

    Args:
        widget (forms.Widget): Widget de Django a estilizar.
        placeholder (str, optional): Texto de placeholder personalizado.
        required (bool, optional): Indica si el campo es obligatorio.
    """
    # Determinar la clase base y el tipo de datos según el widget
    if isinstance(widget, forms.widgets.ClearableFileInput):
        base_class = CLASS_FILE
        data_field = "file"
    elif isinstance(widget, forms.widgets.DateInput):
        widget.input_type = "date"
        widget.format = "%Y-%m-%d"  # Formato ISO para el navegador
        base_class = CLASS_DATE
        data_field = "date"
    elif isinstance(widget, forms.widgets.NumberInput):
        base_class = CLASS_NUMBER
        data_field = "number"
    elif isinstance(widget, forms.widgets.CheckboxInput):
        base_class = CLASS_CHECKBOX
        data_field = "checkbox"
    elif isinstance(widget, forms.widgets.RadioSelect):
        base_class = CLASS_RADIO
        data_field = "radio"
    elif isinstance(widget, forms.widgets.Textarea):
        base_class = CLASS_TEXTAREA
        data_field = "textarea"
    elif isinstance(widget, forms.widgets.Input):
        base_class = CLASS_INPUT
        data_field = "input"
    else:
        base_class = CLASS_SELECT
        data_field = "select"

    # Atributos comunes para todos los widgets
    attrs = {
        "class": base_class,
        "data-field-type": data_field,
    }

    # Agregar placeholder si se proporciona
    if placeholder:
        attrs["placeholder"] = placeholder

    # Marcar visualmente los campos requeridos
    if required:
        attrs["aria-required"] = "true"

    # Actualizar los atributos del widget
    widget.attrs.update(attrs)


def apply_tailwind_style(fields, instance=None):
    """
    Aplica estilos de Tailwind a todos los campos de un formulario.

    Args:
        fields (dict): Diccionario de campos del formulario.
        instance (Model, optional): Instancia de modelo asociada al formulario.
    """
    for name, field in fields.items():
        # Pasar el placeholder y el estado de requerido
        field_placeholder = field.help_text if hasattr(field, "help_text") else None
        field_required = field.required if hasattr(field, "required") else False

        actualizar_widget_attrs(
            field.widget, placeholder=field_placeholder, required=field_required
        )

        # Formatear fechas si hay instancia
        if isinstance(field.widget, forms.widgets.DateInput) and instance:
            value = getattr(instance, name, None)
            if value:
                field.initial = value.strftime("%Y-%m-%d")


# Función adicional para crear placeholder personalizados basados en etiquetas
def generate_placeholders(form):
    """
    Genera placeholders basados en las etiquetas de los campos.

    Args:
        form (Form): Formulario de Django
    """
    for field_name, field in form.fields.items():
        if hasattr(field, "label") and field.label:
            if not field.widget.attrs.get("placeholder"):
                field.widget.attrs["placeholder"] = f"Ingrese {field.label.lower()}"


def disable_field(field, initial_value=None):
    """
    Deshabilita un campo asignándole un valor inicial y añadiéndole clases
    para indicar visualmente que está deshabilitado.

    Args:
        field (forms.Field): Campo de formulario a deshabilitar.
        initial_value: Valor inicial que se asignará al campo.
    """
    if initial_value:
        field.initial = initial_value
    field.disabled = True
    existing_classes = field.widget.attrs.get("class", "")
    disabled_classes = "bg-gray-200 text-gray-600 cursor-not-allowed"
    field.widget.attrs["class"] = f"{existing_classes} {disabled_classes}"
