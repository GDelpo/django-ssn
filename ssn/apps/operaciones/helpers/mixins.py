import logging

from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse

from accounts.middleware import LoginRequiredMixin
from ..models import BaseRequestModel
from .model_utils import get_mapping_model

logger = logging.getLogger("operaciones")


class BreadcrumbsMixin:
    """
    Convierte `self.get_breadcrumbs()` en lista de tuplas (label, url).
    """

    breadcrumbs = []

    def get_breadcrumbs(self):
        return self.breadcrumbs

    def resolve_breadcrumbs(self):
        items = []
        for entry in self.get_breadcrumbs():
            # Aseguramos tupla de largo 2 o 3
            if len(entry) == 2:
                label_obj, url_name = entry
                kwargs_obj = {}
            elif len(entry) == 3:
                label_obj, url_name, kwargs_obj = entry
            else:
                continue

            # Resolvemos label
            label = label_obj(self) if callable(label_obj) else label_obj

            # Resolvemos URL si existe
            if url_name:
                kw = kwargs_obj(self) if callable(kwargs_obj) else kwargs_obj
                url = reverse(url_name, kwargs=kw)
            else:
                url = None

            items.append((label, url))
        return items

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["breadcrumb_items"] = self.resolve_breadcrumbs()
        return ctx


class HeaderButtonsMixin:
    """
    Genera `header_buttons` a partir de `get_header_buttons_config()` y un mapa de fábricas.
    Garantiza que todos los botones tengan una estructura consistente y maneja dependencias de forma segura.
    """

    header_buttons_config = []

    # --- Métodos de creación de botones ---

    def _create_button(self, href, label, **kwargs):
        # Usamos kwargs para que sea más flexible
        button = {
            "id": kwargs.get("id"),
            "href": href,
            "label": label,
            "icon": kwargs.get("icon"),
            "color": kwargs.get("color", "primary"),
            "condition": kwargs.get("condition"),
        }
        return button

    def get_back_button(self, url_name, extra_kwargs=None, use_uuid=True):
        if extra_kwargs is None:
            extra_kwargs = {}
        # MEJORA: Usamos la nueva propiedad segura _base_request_uuid
        if use_uuid and self._base_request_uuid:
            extra_kwargs["uuid"] = self._base_request_uuid

        return self._create_button(
            href=reverse(url_name, kwargs=extra_kwargs),
            label="Volver atrás",
            icon="fas fa-chevron-left",
            color="secondary",
        )

    # NUEVO: Una property que devuelve el UUID de forma segura o None
    @property
    def _base_request_uuid(self):
        if hasattr(self, "base_request") and self.base_request:
            return str(self.base_request.uuid)
        return None

    @property
    def BUTTON_FACTORIES(self):
        factories = {
            "back_base": lambda self: self.get_back_button(
                "operaciones:solicitud_base", use_uuid=False
            ),
            "back_selection": lambda self: self.get_back_button(
                "operaciones:seleccion_tipo_operacion"
            ),
            "back_operations": lambda self: self.get_back_button(
                "operaciones:lista_operaciones"
            ),
            "back_solicitudes": lambda self: self.get_back_button(
                "operaciones:lista_solicitudes", use_uuid=False
            ),
            "new_base": lambda self: self._create_button(
                href=reverse("operaciones:solicitud_base"),
                label="Nueva Solicitud",
                icon="fas fa-plus",
            ),
        }

        # Agregamos las fábricas dependientes del UUID solo si el UUID existe
        if self._base_request_uuid:
            factories.update(
                {
                    "new_operation": lambda self: self._create_button(
                        href=reverse(
                            "operaciones:seleccion_tipo_operacion",
                            kwargs={"uuid": self._base_request_uuid},
                        ),
                        label="Nueva Operación",
                        icon="fas fa-plus",
                    ),
                    "preview": lambda self: self._create_button(
                        href=reverse(
                            "operaciones:preview_operaciones",
                            kwargs={"uuid": self._base_request_uuid},
                        ),
                        label="Revisar Solicitud",
                        icon="fas fa-eye",
                        color="success",
                    ),
                    "send": lambda self: self._create_button(
                        id="enviarSolicitud",
                        href=reverse(
                            "operaciones:enviar_operaciones",
                            kwargs={"uuid": self._base_request_uuid},
                        ),
                        label="Enviar Solicitud",
                        icon="fas fa-paper-plane",
                        color="success",
                    ),
                    "generate_stocks": lambda self: self._create_button(
                        href=reverse(
                            "operaciones:generar_stocks_mensuales",
                            kwargs={"uuid": self._base_request_uuid},
                        ),
                        label="Generar Stocks",
                        icon="fas fa-magic",
                        color="warning",
                    ),
                }
            )
        return factories

    # --- Métodos principales ---

    def get_header_buttons_config(self):
        cfg = self.header_buttons_config
        return cfg() if callable(cfg) else (cfg or [])

    def get_header_buttons(self):
        cfg = self.get_header_buttons_config()
        buttons = []
        for key in cfg:
            factory = self.BUTTON_FACTORIES.get(key)
            # MEJORA: Si la fábrica no existe para esta vista (ej: no hay uuid), la saltea
            if not factory:
                continue

            btn = factory(self)

            # MEJORA: Si la fábrica devuelve None, también la saltea
            if not btn:
                continue

            cond = btn.get("condition")
            if cond is None or cond(self):
                buttons.append(btn)
        return buttons


class BaseRequestRequiredMixin:
    """
    Recupera y valida BaseRequestModel a partir de `uuid` en la URL y la sesión.
    """

    from ..services import SessionService

    def dispatch(self, request, *args, **kwargs):
        url_uuid = kwargs.get("uuid")
        session_uuid = request.session.get("base_request_uuid")

        if not url_uuid:
            messages.error(request, "No se encontró una solicitud activa.")
            return redirect("operaciones:solicitud_base")

        if session_uuid and str(session_uuid) != str(url_uuid):
            messages.warning(
                request,
                "La solicitud no coincide con la sesión; se reinició el proceso.",
            )
            self.SessionService.clear_base_request(request)
            return redirect("operaciones:solicitud_base")

        if not session_uuid:
            request.session["base_request_uuid"] = str(url_uuid)
            request.session.modified = True

        try:
            self.base_request = BaseRequestModel.objects.get(uuid=url_uuid)
        except BaseRequestModel.DoesNotExist:
            messages.error(request, "La solicitud seleccionada no existe.")
            self.SessionService.clear_base_request(request)
            return redirect("operaciones:solicitud_base")

        return super().dispatch(request, *args, **kwargs)


class ContextMixin:
    """
    Agrega al contexto los valores: title, button_text, header_buttons y extra_info.
    """

    title = ""
    button_text = ""

    def get_title(self):
        return self.title

    def get_button_text(self):
        return self.button_text

    def get_header_buttons(self):
        # Por defecto, sin botones. Se sobrescribe con HeaderButtonsMixin.
        return []

    def get_extra_info(self):
        from ..services import OperacionesService

        if hasattr(self, "base_request"):
            return OperacionesService.get_extra_info(self.base_request)
        return ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "title": self.get_title(),
                "button_text": self.get_button_text(),
                "header_buttons": self.get_header_buttons(),
                "extra_info": self.get_extra_info(),
            }
        )
        if hasattr(self, "base_request"):
            context["base_request"] = self.base_request
        return context


class DynamicModelMixin:
    """
    Selecciona dinámicamente el modelo según `tipo_operacion` en la URL.
    """

    def get_model_class(self):
        tipo = self.kwargs.get("tipo_operacion")
        model = get_mapping_model().get(tipo)
        if not model:
            messages.error(self.request, "Tipo de operación inválido.")
            raise Http404()
        return model

    def get_queryset(self):
        return self.get_model_class().objects.all()

    def get_object(self, queryset=None):
        return get_object_or_404(
            queryset or self.get_queryset(), pk=self.kwargs.get("pk")
        )


class EditableStateRequiredMixin:
    """
    Bloquea el dispatch si la solicitud NO está en un estado editable
    (Borrador o Rectificando).
    """

    def dispatch(self, request, *args, **kwargs):
        # Asumimos que BaseRequestRequiredMixin ya se ejecutó y tenemos self.base_request
        if hasattr(self, "base_request") and not self.base_request.is_editable:
            messages.error(
                request,
                "Esta solicitud ya fue enviada y no se puede modificar a menos que se inicie una rectificación.",
            )
            return redirect(
                "operaciones:lista_operaciones", uuid=str(self.base_request.uuid)
            )
        return super().dispatch(request, *args, **kwargs)


class StandaloneViewMixin(
    LoginRequiredMixin,
    BreadcrumbsMixin,
    HeaderButtonsMixin,
    ContextMixin,
):
    """
    Mixin base para todas las vistas que requieren autenticación.
    Incluye breadcrumbs, botones de header y contexto común.

    Vistas que NO usan base_request en la URL:
      - SolicitudBaseCreateView (path '')
      - SolicitudBaseListView (path 'solicitudes/')
      - SolicitudRespuestaDetailView (path 'solicitudes/respuesta/...')
    """

    pass


class OperationReadonlyViewMixin(StandaloneViewMixin, BaseRequestRequiredMixin):
    """Mixin base para TODAS las vistas de solo lectura/listados/previews/envíos."""

    pass


class OperationEditViewMixin(
    OperationReadonlyViewMixin,
    EditableStateRequiredMixin,
):
    """Mixin para vistas de creación, edición y eliminación (bloquea tras envío)."""

    pass
