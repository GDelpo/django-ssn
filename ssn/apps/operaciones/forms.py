import datetime
import logging

from django import forms
from django.conf import settings

from .helpers import (
    CLASS_SELECT,
    apply_tailwind_style,
    disable_field,
    generate_monthly_options_with_overlap,
    generate_week_options_with_overlap,
    get_default_cronograma,
    get_last_week_id,
    get_mapping_model,
)
from .models import BaseRequestModel, DetalleOperacionCanje, TipoOperacion
from .models.choices import EstadoSolicitud, TipoEntrega
from .services import SolicitudValidationService

# Configuración del logger
logger = logging.getLogger("operaciones")


class BaseRequestForm(forms.ModelForm):
    """
    Formulario para crear o actualizar la solicitud base.
    Contiene información común para todas las operaciones y maneja el cronograma.
    """

    # Definimos dos campos extra: uno para el cronograma semanal y otro para el mensual.
    cronograma_semanal = forms.ChoiceField(
        label="Cronograma Semanal",
        widget=forms.Select(
            attrs={
                "class": CLASS_SELECT,
                "data-field-type": "select",
                "id": "cronograma_semanal",
            }
        ),
        choices=generate_week_options_with_overlap(datetime.date.today().year),
        required=False,
    )
    cronograma_mensual = forms.ChoiceField(
        label="Cronograma Mensual",
        widget=forms.Select(
            attrs={
                "class": CLASS_SELECT,
                "data-field-type": "select",
                "id": "cronograma_mensual",
            }
        ),
        choices=generate_monthly_options_with_overlap(datetime.date.today().year),
        required=False,
    )

    class Meta:
        model = BaseRequestModel
        exclude = ["cronograma", "send_at", "estado", "updated_at"]

    def __init__(self, *args, **kwargs):
        """
        Inicializa el formulario, aplicando estilos y configurando valores iniciales.
        """
        super().__init__(*args, **kwargs)

        # Aplicar estilos Tailwind a todos los campos
        apply_tailwind_style(self.fields, instance=self.instance)

        # Configurar campos específicos
        if "codigo_compania" in self.fields:
            disable_field(self.fields["codigo_compania"], settings.SSN_API_CIA)
            logger.debug(
                f"Campo 'codigo_compania' deshabilitado y establecido a '{settings.SSN_API_CIA}'"
            )

        # Establecer valores iniciales para cronograma
        week_choices = self.fields["cronograma_semanal"].choices
        self.fields["cronograma_semanal"].initial = get_last_week_id(week_choices)
        self.fields["cronograma_mensual"].initial = get_default_cronograma("Mensual")

        logger.debug(
            f"BaseRequestForm inicializado para instancia: {self.instance.pk if self.instance else 'nueva'}"
        )

    def clean(self):
        """
        Valida que se haya seleccionado un cronograma apropiado según el tipo de entrega.

        Returns:
            dict: Datos validados del formulario

        Raises:
            ValidationError: Si no se selecciona un cronograma válido
        """
        logger.info("=== INICIO BaseRequestForm.clean() ===")
        
        cleaned_data = super().clean()
        tipo_entrega = cleaned_data.get("tipo_entrega")

        logger.debug(f"Validando formulario con tipo de entrega: {tipo_entrega}")

        # Seleccionar el tipo de cronograma según el tipo de entrega
        if tipo_entrega == "Semanal":
            seleccionado = cleaned_data.get("cronograma_semanal")
        elif tipo_entrega == "Mensual":
            seleccionado = cleaned_data.get("cronograma_mensual")
        else:
            seleccionado = None
            logger.warning(f"Tipo de entrega no reconocido: {tipo_entrega}")

        # Manejar el caso en que seleccionado sea una lista
        if isinstance(seleccionado, list):
            seleccionado = seleccionado[0]

        # Validar que se haya seleccionado un cronograma
        if not seleccionado:
            logger.warning("No se seleccionó un cronograma válido")
            raise forms.ValidationError(
                "Debe seleccionar un cronograma según el tipo de entrega."
            )

        # Usar el servicio de validación centralizado
        is_new_instance = self.instance._state.adding
        exclude_pk = None if is_new_instance else self.instance.pk
        
        # Solo validar completamente para nuevas instancias
        if is_new_instance:
            validation_errors, validation_warnings = SolicitudValidationService.validate_new_solicitud(
                cronograma=seleccionado,
                tipo_entrega=tipo_entrega,
                exclude_pk=exclude_pk,
            )
            
            # Guardar warnings para que la vista los muestre como mensajes
            self._validation_warnings = validation_warnings
            
            for error in validation_errors:
                if error.field_name:
                    self.add_error(error.field_name, error.error_message)
                else:
                    raise forms.ValidationError(error.error_message)
        else:
            # Para ediciones, solo validar duplicados
            result = SolicitudValidationService.validate_no_duplicate(
                cronograma=seleccionado,
                tipo_entrega=tipo_entrega,
                exclude_pk=exclude_pk,
            )
            if not result.is_valid:
                self.add_error(result.field_name, result.error_message)

        # Guardar el cronograma en los datos validados
        cleaned_data["cronograma"] = seleccionado
        logger.debug(f"Cronograma seleccionado: {seleccionado}")

        return cleaned_data

    def save(self, commit=True):
        """
        Guarda la instancia del formulario, asegurando que el cronograma sea establecido.

        Args:
            commit: Indica si se debe guardar en la base de datos

        Returns:
            BaseRequestModel: Instancia actualizada
        """
        instance = super().save(commit=False)
        instance.cronograma = self.cleaned_data.get("cronograma")

        if commit:
            instance.save()
            logger.info(f"Solicitud base guardada con UUID: {instance.uuid}")

        return instance


class TipoOperacionForm(forms.Form):
    """
    Formulario para seleccionar el tipo de operación a realizar.
    Punto de partida para la creación de operaciones específicas.
    """

    tipo_operacion = forms.ChoiceField(
        choices=TipoOperacion.choices,
        label="Selecciona el tipo de operación",
        widget=forms.Select(attrs={"class": CLASS_SELECT, "data-field-type": "select"}),
    )


class DetalleOperacionCanjeForm(forms.ModelForm):
    """
    Formulario para manejar los detalles de una operación de canje.
    Se usa como subformulario en operaciones de tipo 'J'.
    """

    class Meta:
        model = DetalleOperacionCanje
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        """
        Inicializa el formulario aplicando estilos Tailwind.
        """
        super().__init__(*args, **kwargs)
        apply_tailwind_style(self.fields, instance=self.instance)
        logger.debug(
            f"DetalleOperacionCanjeForm inicializado: prefix={kwargs.get('prefix', 'ninguno')}"
        )


def create_operacion_form(tipo_operacion):
    """
    Crea dinámicamente un formulario específico para el tipo de operación proporcionado.

    Args:
        tipo_operacion: Código que identifica el tipo de operación

    Returns:
        Form class: Clase de formulario específica para el tipo de operación

    Raises:
        ValueError: Si el tipo de operación no es válido
    """
    logger.debug(f"Creando formulario para tipo de operación: {tipo_operacion}")

    # Obtener el mapeo de modelos y la clase correspondiente
    mapping = get_mapping_model()
    model_class = mapping.get(tipo_operacion)

    if not model_class:
        logger.error(f"Tipo de operación no válida: {tipo_operacion}")
        raise ValueError(f"Tipo de operación no válida: {tipo_operacion}")

    # Definimos las opciones Meta base según el tipo de operación
    meta_options = {"model": model_class}
    if tipo_operacion == "J":
        meta_options["exclude"] = ["detalle_a", "detalle_b"]
        logger.debug("Configurando formulario para canje (J) con exclusión de detalles")
    elif tipo_operacion in ["SI", "SP", "SC"]:
        # Stocks mensuales - excluir campos de relación
        meta_options["exclude"] = ["solicitud"]
        logger.debug(f"Configurando formulario para stock mensual tipo: {tipo_operacion}")
    else:
        meta_options["exclude"] = ["solicitud"]
        logger.debug(f"Configurando formulario estándar para tipo: {tipo_operacion}")

    # Creamos la clase Meta de forma dinámica
    MetaClass = type("Meta", (), meta_options)

    class DynamicOperacionForm(forms.ModelForm):
        """
        Formulario dinámicamente generado para un tipo específico de operación.
        """

        Meta = MetaClass

        def __init__(self, *args, **kwargs):
            """
            Inicializa el formulario y configura campos según el tipo de operación.
            """
            super().__init__(*args, **kwargs)

            # Aplica estilos generales a todos los campos
            apply_tailwind_style(self.fields, instance=self.instance)

            # Deshabilitamos y asignamos valores fijos a ciertos campos
            if "tipo_operacion" in self.fields:
                disable_field(self.fields["tipo_operacion"], tipo_operacion)

            if "codigo_afectacion" in self.fields:
                disable_field(self.fields["codigo_afectacion"], "999")

            if "tipo_valuacion" in self.fields:
                self.fields["tipo_valuacion"].initial = "V"

            logger.debug(
                f"Formulario configurado para instancia {self.instance.pk if self.instance else 'nueva'}"
            )

            # Si es Canje (J), instanciamos dos subformularios para detalle A y detalle B
            if tipo_operacion == "J":
                self._setup_canje_subforms()

        def _setup_canje_subforms(self):
            """
            Configura los subformularios para operaciones de canje.
            """
            # Importamos el formulario para el detalle del canje
            from .forms import DetalleOperacionCanjeForm

            logger.debug("Configurando subformularios para operación de canje")

            if self.instance and self.instance.pk:
                # Si tenemos una instancia existente, usamos sus detalles
                self.detalle_a_form = DetalleOperacionCanjeForm(
                    instance=self.instance.detalle_a, prefix="a"
                )
                self.detalle_b_form = DetalleOperacionCanjeForm(
                    instance=self.instance.detalle_b, prefix="b"
                )
                logger.debug(
                    f"Subformularios creados para canje existente ID: {self.instance.pk}"
                )
            else:
                # Si es una nueva instancia, creamos formularios vacíos
                self.detalle_a_form = DetalleOperacionCanjeForm(prefix="a")
                self.detalle_b_form = DetalleOperacionCanjeForm(prefix="b")
                logger.debug("Subformularios creados para nuevo canje")

        def clean(self):
            """
            Valida los datos del formulario, incluyendo subformularios si es un canje.

            Returns:
                dict: Datos validados
            """
            cleaned_data = super().clean()

            # Validación específica para formularios de canje
            if hasattr(self, "detalle_a_form") and hasattr(self, "detalle_b_form"):
                if not self.detalle_a_form.is_valid():
                    logger.warning("Errores en subformulario detalle A")
                    for field, errors in self.detalle_a_form.errors.items():
                        for error in errors:
                            logger.debug(
                                f"Error en detalle A - campo '{field}': {error}"
                            )
                    raise forms.ValidationError(
                        "Hay errores en el detalle A del canje."
                    )

                if not self.detalle_b_form.is_valid():
                    logger.warning("Errores en subformulario detalle B")
                    for field, errors in self.detalle_b_form.errors.items():
                        for error in errors:
                            logger.debug(
                                f"Error en detalle B - campo '{field}': {error}"
                            )
                    raise forms.ValidationError(
                        "Hay errores en el detalle B del canje."
                    )

            return cleaned_data

        def save(self, commit=True):
            """
            Guarda el formulario y sus subformularios si es un canje.

            Args:
                commit: Indica si se debe guardar en la base de datos

            Returns:
                Model: Instancia del modelo
            """
            instance = super().save(commit=False)

            # Manejar el guardado de los subformularios en operaciones de canje
            if hasattr(self, "detalle_a_form") and hasattr(self, "detalle_b_form"):
                # Guardar los detalles sin commit
                detalle_a = self.detalle_a_form.save(commit=False)
                detalle_b = self.detalle_b_form.save(commit=False)

                if commit:
                    # Guardar los detalles
                    detalle_a.save()
                    detalle_b.save()

                    # Asociarlos a la instancia principal
                    instance.detalle_a = detalle_a
                    instance.detalle_b = detalle_b

                    # Guardar la instancia principal
                    instance.save()
                    logger.info(f"Operación de canje guardada con ID: {instance.pk}")

                    return instance

            # Para operaciones que no son canje o si no se requiere commit
            if commit:
                instance.save()
                logger.info(
                    f"Operación tipo {instance.tipo_operacion} guardada con ID: {instance.pk}"
                )

            return instance

    logger.debug(f"Formulario dinámico creado exitosamente para tipo: {tipo_operacion}")
    return DynamicOperacionForm


class SolicitudFilterForm(forms.Form):
    """
    Formulario para filtrar y ordenar la lista de solicitudes.
    """

    ORDEN_CHOICES = [
        ("-created_at", "Más recientes primero"),
        ("created_at", "Más antiguos primero"),
        ("cronograma", "Cronograma (A-Z)"),
        ("-cronograma", "Cronograma (Z-A)"),
        ("tipo_entrega", "Tipo de entrega (A-Z)"),
        ("-tipo_entrega", "Tipo de entrega (Z-A)"),
    ]

    tipo_entrega = forms.ChoiceField(
        label="Tipo de Entrega",
        required=False,
        choices=[("", "Todos")] + list(TipoEntrega.choices),
        widget=forms.Select(
            attrs={
                "class": CLASS_SELECT,
                "data-field-type": "select",
            }
        ),
    )

    estado = forms.ChoiceField(
        label="Estado",
        required=False,
        choices=[("", "Todos")] + list(EstadoSolicitud.choices),
        widget=forms.Select(
            attrs={
                "class": CLASS_SELECT,
                "data-field-type": "select",
            }
        ),
    )

    anio = forms.ChoiceField(
        label="Año",
        required=False,
        widget=forms.Select(
            attrs={
                "class": CLASS_SELECT,
                "data-field-type": "select",
            }
        ),
    )

    orden = forms.ChoiceField(
        label="Ordenar por",
        required=False,
        choices=ORDEN_CHOICES,
        initial="-created_at",
        widget=forms.Select(
            attrs={
                "class": CLASS_SELECT,
                "data-field-type": "select",
            }
        ),
    )

    def __init__(self, *args, anios_disponibles=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Generar opciones de año dinámicamente
        if anios_disponibles:
            self.fields["anio"].choices = [("", "Todos")] + [
                (str(anio), str(anio)) for anio in anios_disponibles
            ]
        else:
            # Default: años desde 2024 hasta el actual
            current_year = datetime.date.today().year
            self.fields["anio"].choices = [("", "Todos")] + [
                (str(y), str(y)) for y in range(current_year, 2023, -1)
            ]
