import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Exists, OuterRef
from django.http import FileResponse, Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
)
from ssn_client.models import SolicitudResponse
from ssn_client.services import (
    consultar_estado_ssn,
    enviar_y_guardar_solicitud,
    solicitar_rectificacion_ssn,
)
from ssn_client.services import EstadoSSN

from .forms import BaseRequestForm, SolicitudFilterForm, TipoOperacionForm, create_operacion_form
from .helpers import (
    DynamicModelMixin,
    OperationEditViewMixin,
    OperationReadonlyViewMixin,
    StandaloneViewMixin,
)
from .helpers.form_styles import disable_field
from .helpers.text_utils import pretty_json
from .models import BaseRequestModel, EstadoSolicitud, TipoEntrega
from .services import (
    OperacionesService,
    SessionService,
    SolicitudPreviewService,
    MonthlyReportGeneratorService,
)

logger = logging.getLogger("operaciones")


class SolicitudBaseCreateView(
    StandaloneViewMixin,
    SuccessMessageMixin,
    CreateView,
):
    # --- Atributos configurables ---
    model = BaseRequestModel
    form_class = BaseRequestForm
    template_name = "forms/solicitud.html"
    title = "Formulario de Solicitud"
    button_text = "Agregar Operaciones"
    header_buttons_config = []
    breadcrumbs = [
        ("Inicio", "theme:index"),
        ("Nueva Solicitud", None),
    ]
    success_message = "Solicitud base creada exitosamente."

    def get(self, request, *args, **kwargs):
        recover_uuid = request.GET.get("recover_uuid")
        if recover_uuid:
            logger.debug(f"Intentando recuperar solicitud con UUID: {recover_uuid}")
            try:
                base_instance = BaseRequestModel.objects.get(uuid=recover_uuid)

                # Sincronizar estado con SSN al recuperar
                self._sync_estado_ssn(base_instance)

                SessionService.set_base_request(request, base_instance)
                logger.debug(f"Solicitud {recover_uuid} recuperada.")
                messages.success(request, "Solicitud recuperada exitosamente.")
                
                # Redirigir según tipo: mensual a lista, semanal a selección
                if base_instance.tipo_entrega == TipoEntrega.MENSUAL:
                    return redirect(
                        "operaciones:lista_operaciones", uuid=base_instance.uuid
                    )
                else:
                    return redirect(
                        "operaciones:seleccion_tipo_operacion", uuid=base_instance.uuid
                    )
            except BaseRequestModel.DoesNotExist:
                logger.warning(
                    f"Intento de recuperar UUID no existente: {recover_uuid}"
                )
                messages.error(
                    request, "No se encontró una operación con el UUID proporcionado."
                )
        return super().get(request, *args, **kwargs)

    def get_initial(self):
        """Pre-setea valores desde parámetros GET (para alertas de vencimiento)."""
        initial = super().get_initial()
        
        # Pre-setear tipo_entrega y cronograma desde GET
        tipo_entrega = self.request.GET.get("tipo_entrega")
        cronograma = self.request.GET.get("cronograma")
        
        if tipo_entrega:
            initial["tipo_entrega"] = tipo_entrega
            if cronograma:
                if tipo_entrega == "Semanal":
                    initial["cronograma_semanal"] = cronograma
                elif tipo_entrega == "Mensual":
                    initial["cronograma_mensual"] = cronograma
        
        return initial

    def _sync_estado_ssn(self, base_instance):
        """
        Sincroniza el estado de la solicitud con la SSN.
        Delega al método del modelo para evitar duplicación de código.
        """
        base_instance.sync_estado_con_ssn()

    def form_valid(self, form):
        # La validación de datos para mensual ya se hace en el servicio de validación
        # llamado desde form.clean(), así que aquí solo procesamos el guardado
        
        response = super().form_valid(form)
        # No sincronizar al crear nuevas solicitudes en BORRADOR
        # El estado se sincronizará solo cuando se envíe a SSN
        SessionService.set_base_request(self.request, self.object)
        
        # Mostrar advertencias de validación (ej: SSN no disponible)
        for warning in getattr(form, '_validation_warnings', []):
            messages.warning(self.request, warning)
        
        # Si es mensual, generar stocks automáticamente
        if self.object.tipo_entrega == TipoEntrega.MENSUAL:
            result = MonthlyReportGeneratorService.generate_monthly_stocks(self.object)
            if result.success:
                messages.success(
                    self.request,
                    f"Stocks generados automáticamente: {result.inversiones_count} inversiones, "
                    f"{result.plazos_fijos_count} plazos fijos, {result.cheques_pd_count} cheques PD."
                )
                for warning in result.warnings:
                    messages.warning(self.request, warning)
            else:
                messages.warning(
                    self.request,
                    f"No se pudieron generar stocks automáticamente: {result.message}"
                )
        
        return response

    def get_success_url(self):
        # Semanal va a selección de tipo de operación
        # Mensual va a lista de operaciones (stocks ya generados)
        if self.object.tipo_entrega == TipoEntrega.MENSUAL:
            return reverse(
                "operaciones:lista_operaciones",
                kwargs={"uuid": str(self.object.uuid)},
            )
        else:
            return reverse(
                "operaciones:seleccion_tipo_operacion",
                kwargs={"uuid": str(self.object.uuid)},
            )

    def form_invalid(self, form):
        """
        Muestra los errores del formulario también como mensajes toast.
        """
        # Errores de campos específicos
        for field, errors in form.errors.items():
            for error in errors:
                if field == "__all__":
                    messages.error(self.request, error)
                else:
                    # Obtener el label del campo si existe
                    field_label = form.fields.get(field, None)
                    if field_label and hasattr(field_label, 'label'):
                        messages.error(self.request, f"{field_label.label}: {error}")
                    else:
                        messages.error(self.request, error)
        
        return super().form_invalid(form)


class SolicitudBaseListView(
    StandaloneViewMixin,
    ListView,
):
    # --- Atributos configurables ---
    model = BaseRequestModel
    template_name = "lists/lista_solicitudes.html"
    context_object_name = "solicitudes"
    paginate_by = 10
    title = "Listado de Solicitudes"
    header_buttons_config = ["new_base"]
    breadcrumbs = [
        ("Inicio", "theme:index"),
        ("Listado de Solicitudes", None),
    ]

    def get_filter_form(self):
        """Crea el formulario de filtros con los años disponibles."""
        # Obtener años únicos de las solicitudes existentes
        anios = (
            BaseRequestModel.objects.values_list("cronograma", flat=True)
            .distinct()
        )
        anios_unicos = sorted(
            set(c[:4] for c in anios if c), reverse=True
        )
        return SolicitudFilterForm(
            self.request.GET or None, 
            anios_disponibles=anios_unicos
        )

    def get_queryset(self):
        SessionService.clear_base_request(self.request)
        
        # Queryset base con prefetch y annotate
        qs = (
            BaseRequestModel.objects.all()
            .prefetch_related("respuestas")
            .annotate(
                tiene_error=Exists(
                    SolicitudResponse.objects.filter(
                        solicitud=OuterRef("pk"),
                        es_error=True,
                    )
                )
            )
        )

        # Aplicar filtros desde GET params
        tipo_entrega = self.request.GET.get("tipo_entrega")
        estado = self.request.GET.get("estado")
        anio = self.request.GET.get("anio")
        orden = self.request.GET.get("orden", "-created_at")

        if tipo_entrega:
            qs = qs.filter(tipo_entrega=tipo_entrega)
        
        if estado:
            qs = qs.filter(estado=estado)
        
        if anio:
            qs = qs.filter(cronograma__startswith=anio)

        # Aplicar ordenamiento
        if orden:
            qs = qs.order_by(orden)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = self.get_filter_form()
        # Orden actual para los encabezados de la tabla
        context["current_orden"] = self.request.GET.get("orden", "-created_at")
        # Preservar query params para paginación (sin page ni orden)
        query_params = self.request.GET.copy()
        if "page" in query_params:
            del query_params["page"]
        if "orden" in query_params:
            del query_params["orden"]
        context["query_params"] = query_params.urlencode()
        return context


class OperacionListView(
    OperationReadonlyViewMixin,
    ListView,
):
    # --- Atributos configurables (sin cambios) ---
    template_name = "lists/lista_op.html"
    context_object_name = "operations"
    paginate_by = 10
    title = "Listado de Operaciones"
    breadcrumbs = [
        ("Inicio", "theme:index"),
        ("Solicitudes", "operaciones:lista_solicitudes"),
        (lambda self: f"Solicitud {self.base_request.uuid}", None),
    ]


    # --- Métodos ---
    def get_title(self):
        # Si está en modo rectificación, añadirlo al título
        if self.base_request.estado == EstadoSolicitud.A_RECTIFICAR:
            return f"{self.title} (Rectificando)"
        return self.title

    def get(self, request, *args, **kwargs):
        """
        Sincroniza el estado con SSN antes de mostrar la lista.
        """
        self._sync_estado_con_ssn()
        return super().get(request, *args, **kwargs)

    def _sync_estado_con_ssn(self):
        """
        Consulta el estado SSN y actualiza el estado local si es necesario.
        """
        cambio = self.base_request.sync_estado_con_ssn()
        
        # Si hubo cambio, notificar al usuario
        if cambio:
            messages.info(
                self.request,
                f"Estado actualizado: {self.base_request.get_estado_display()}",
            )

    def get_queryset(self):
        return OperacionesService.get_all_operaciones(self.base_request)

    def get_header_buttons_config(self):
        has_ops = bool(self.get_queryset())
        is_monthly = self.base_request.tipo_entrega == TipoEntrega.MENSUAL

        if not self.base_request.is_editable:
            # Para estados no editables (PRESENTADO, RECTIFICACION_PENDIENTE)
            return ["back_solicitudes", "preview"]
        else:
            # Para estados editables (BORRADOR, CARGADO, A_RECTIFICAR)
            buttons = ["back_solicitudes"]
            
            # Para semanales, permitir agregar nuevas operaciones
            if not is_monthly:
                buttons.append("new_operation")
            
            # Agregar preview si hay operaciones/stocks
            if has_ops:
                buttons.append("preview")
            
            return buttons

    def get_header_buttons(self):
        buttons = super().get_header_buttons()

        if self.base_request.estado == EstadoSolicitud.A_RECTIFICAR:
            has_changes = OperacionesService.has_changes_since_rectification(
                self.base_request
            )

            if has_changes:
                for button in buttons:
                    # Buscamos por '/preview/'
                    if button.get("href") and "/preview/" in button["href"]:
                        button["label"] = "Revisar Cambios"
                        button["color"] = "warning"
                        break

        return buttons

    def post(self, request, *args, **kwargs):
        """
        Maneja las acciones de Iniciar y Cancelar la rectificación.
        
        Flujo de rectificación:
        1. PRESENTADO -> Solicitar rectificación a SSN -> RECTIFICACION_PENDIENTE
        2. SSN aprueba -> A_RECTIFICAR (editable)
        3. Usuario envía cambios -> PRESENTADO
        """
        # --- Acción para INICIAR la rectificación ---
        if "rectify_action" in request.POST:
            # Consultar estado SSN actual
            estado_ssn, datos_ssn, status_consulta = consultar_estado_ssn(
                self.base_request
            )

            if status_consulta >= 400:
                error_detail = datos_ssn.get('error') or datos_ssn.get('message', 'Error desconocido')
                msg = f"No se pudo verificar el estado en SSN: {error_detail}"
                messages.error(request, msg)
                return redirect(request.path)

            # Si está PRESENTADO → Solicitar rectificación
            if estado_ssn == EstadoSSN.PRESENTADO:
                # Pasamos el estado ya conocido para evitar una consulta redundante a la SSN
                response_data, status, _ = solicitar_rectificacion_ssn(
                    self.base_request, estado_ssn_conocido=estado_ssn
                )

                if 200 <= status < 300:
                    messages.success(
                        request,
                        "Solicitud de rectificación enviada exitosamente.",
                    )
                    messages.info(
                        request,
                        "Estado: RECTIFICACIÓN PENDIENTE. Deberá esperar a que la SSN apruebe "
                        "para poder editar las operaciones.",
                    )
                else:
                    messages.error(
                        request,
                        f"Error al solicitar rectificación: {response_data.get('error', 'Error desconocido')}",
                    )
                return redirect(request.path)

            # Si está A_RECTIFICAR → Ya puede editar
            elif estado_ssn == EstadoSSN.A_RECTIFICAR:
                self.base_request.estado = EstadoSolicitud.A_RECTIFICAR
                self.base_request.save()
                messages.success(
                    request,
                    "Modo de rectificación activado. Puede editar las operaciones.",
                )

            # Si está RECTIFICACION_PENDIENTE → No puede editar aún
            elif estado_ssn == EstadoSSN.RECTIFICACION_PENDIENTE:
                self.base_request.estado = EstadoSolicitud.RECTIFICACION_PENDIENTE
                self.base_request.save()
                messages.warning(
                    request,
                    "La rectificación está pendiente de aprobación por la SSN. "
                    "No se puede editar hasta que sea aprobada.",
                )

            # Si está CARGADO → Puede editar directamente
            elif estado_ssn == EstadoSSN.CARGADO:
                self.base_request.estado = EstadoSolicitud.CARGADO
                self.base_request.save()
                messages.success(
                    request,
                    "Puede continuar editando. Los datos aún no están confirmados en SSN.",
                )

            # Otros estados
            else:
                messages.info(
                    request,
                    f"Estado actual en SSN: {estado_ssn}. No requiere rectificación.",
                )

        # --- Acción para CANCELAR la rectificación ---
        elif "cancel_rectify_action" in request.POST:
            if self.base_request.estado in [
                EstadoSolicitud.A_RECTIFICAR,
                EstadoSolicitud.CARGADO,
            ]:
                OperacionesService.revert_new_operations(self.base_request)
                # Sincronizar estado con SSN para obtener el estado real
                self.base_request.sync_estado_con_ssn()
                messages.success(
                    request,
                    "La rectificación ha sido cancelada y las operaciones nuevas fueron descartadas.",
                )

        return redirect(request.path)

    def get_context_data(self, **kwargs):
        """
        Añade la variable 'has_changes' al contexto para estados que lo requieren.
        """
        context = super().get_context_data(**kwargs)
        
        # Agregar has_changes solo para estados de rectificación activa
        if self.base_request.estado == EstadoSolicitud.A_RECTIFICAR:
            context["has_changes"] = OperacionesService.has_changes_since_rectification(
                self.base_request
            )
        
        return context


class TipoOperacionSelectView(
    OperationReadonlyViewMixin,
    FormView,
):
    # --- Atributos configurables ---
    form_class = TipoOperacionForm
    template_name = "forms/seleccion_tipo_operacion.html"
    title = "Tipo de Operación"
    button_text = "Crear Operación"
    header_buttons_config = ["back_base"]
    breadcrumbs = [
        ("Inicio", "theme:index"),
        ("Solicitud Base", "operaciones:solicitud_base"),
        ("Seleccionar Tipo", None),
    ]

    # --- Métodos ---
    def dispatch(self, request, *args, **kwargs):
        """Bloquear acceso si la solicitud es mensual (redirigir a lista)."""
        response = super().dispatch(request, *args, **kwargs)
        if self.base_request.tipo_entrega == TipoEntrega.MENSUAL:
            # Mensual no necesita seleccionar tipo, los stocks ya fueron generados
            return redirect(
                "operaciones:lista_operaciones",
                uuid=self.base_request.uuid,
            )
        return response

    def form_valid(self, form):
        tipo = form.cleaned_data["tipo_operacion"]
        return redirect(
            "operaciones:crear_operacion",
            uuid=str(self.base_request.uuid),
            tipo_operacion=tipo,
        )


class OperacionCreateView(
    OperationEditViewMixin,
    SuccessMessageMixin,
    CreateView,
):
    # --- Atributos configurables ---
    template_name = "forms/operacion.html"
    title = "Formulario de Operación"
    button_text = "Guardar Operación"
    header_buttons_config = ["back_selection"]
    breadcrumbs = [
        (
            lambda self: f"Solicitud {self.base_request.uuid}",
            "operaciones:lista_operaciones",
            lambda self: {"uuid": self.base_request.uuid},
        ),
        (
            "Tipo de Operación",
            "operaciones:seleccion_tipo_operacion",
            lambda self: {"uuid": self.base_request.uuid},
        ),
        ("Nueva Operación", None),
    ]
    success_message = "Operación creada correctamente."

    def dispatch(self, request, *args, **kwargs):
        self.tipo_operacion = kwargs.get("tipo_operacion")
        self.form_class = create_operacion_form(self.tipo_operacion)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.solicitud = self.base_request
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            "operaciones:lista_operaciones",
            kwargs={"uuid": str(self.base_request.uuid)},
        )


class OperacionDetailView(
    OperationReadonlyViewMixin,
    DynamicModelMixin,
    DetailView,
):
    # --- Atributos configurables ---
    template_name = "forms/operacion_readonly.html"
    context_object_name = "operation"
    title = "Detalles de Operación"
    header_buttons_config = ["back_operations"]
    breadcrumbs = [
        ("Inicio", "theme:index"),
        ("Solicitudes", "operaciones:lista_solicitudes"),
        (
            lambda self: f"Solicitud {self.base_request.uuid}",
            "operaciones:lista_operaciones",
            lambda self: {"uuid": self.base_request.uuid},
        ),
        ("Ver Detalle", None),
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        tipo_operacion = self.object.tipo_operacion
        # Crea el formulario dinámicamente según el tipo de operación
        FormClass = create_operacion_form(tipo_operacion)
        form = FormClass(instance=self.object)
        # Deshabilitar campos del formulario principal
        for field in form.fields.values():
            disable_field(field)
        # Deshabilitar campos de subformularios si existen
        for subform_name in ["detalle_a_form", "detalle_b_form"]:
            subform = getattr(form, subform_name, None)
            if subform:
                for field in subform.fields.values():
                    disable_field(field)
        context["form"] = form
        return context


class OperacionUpdateView(
    OperationEditViewMixin,
    DynamicModelMixin,
    SuccessMessageMixin,
    UpdateView,
):
    # --- Atributos configurables ---
    template_name = "forms/operacion.html"
    title = "Editar Operación"
    button_text = "Actualizar Operación"
    header_buttons_config = ["back_operations"]
    breadcrumbs = [
        ("Inicio", "theme:index"),
        ("Solicitudes", "operaciones:lista_solicitudes"),
        (
            lambda self: f"Solicitud {self.base_request.uuid}",
            "operaciones:lista_operaciones",
            lambda self: {"uuid": self.base_request.uuid},
        ),
        ("Editar Operación", None),
    ]
    success_message = "Operación actualizada correctamente."

    def dispatch(self, request, *args, **kwargs):
        self.tipo_operacion = kwargs.get("tipo_operacion")
        return super().dispatch(request, *args, **kwargs)

    def get_form_class(self):
        return create_operacion_form(self.tipo_operacion)

    def get_success_url(self):
        return reverse(
            "operaciones:lista_operaciones",
            kwargs={"uuid": str(self.base_request.uuid)},
        )


class OperacionDeleteView(
    OperationEditViewMixin,
    DynamicModelMixin,
    DeleteView,
):
    # --- Atributos configurables ---
    template_name = "forms/operacion_confirm_delete.html"
    title = "Eliminar Operación"
    button_text = "Eliminar Operación"
    header_buttons_config = ["back_operations"]
    breadcrumbs = [
        ("Inicio", "theme:index"),
        ("Solicitudes", "operaciones:lista_solicitudes"),
        (
            lambda self: f"Solicitud {self.base_request.uuid}",
            "operaciones:lista_operaciones",
            lambda self: {"uuid": self.base_request.uuid},
        ),
        ("Eliminar Operación", None),
    ]

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Operación eliminada correctamente.")
        return super().delete(request, *args, **kwargs)

    def get_success_url(self):
        return reverse(
            "operaciones:lista_operaciones",
            kwargs={"uuid": str(self.base_request.uuid)},
        )


class OperacionPreviewView(
    OperationReadonlyViewMixin,
    TemplateView,
):
    # --- Atributos configurables ---
    template_name = "preview.html"
    title = "Vista Previa de Solicitud"

    def get_header_buttons_config(self):
        return ["back_operations"] + (["send"] if self.base_request.is_editable else [])

    def get(self, request, *args, **kwargs):
        operations = OperacionesService.get_all_operaciones(self.base_request)
        preview = SolicitudPreviewService(self.base_request, operations)
        if not preview.generar_preview():
            messages.error(request, "No hay operaciones para enviar.")
            return redirect(
                "operaciones:lista_operaciones", uuid=str(self.base_request.uuid)
            )
        self.formatted_json = preview.formatted_json
        self.mailto_link = preview.mailto_link
        self.excel_link = preview.generar_excel()
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "formatted_json": self.formatted_json,
                "mailto_link": self.mailto_link,
                "excel_link": self.excel_link,
            }
        )
        return context


class ExcelDownloadView(
    OperationReadonlyViewMixin,
    View,
):
    """Sirve el archivo Excel de preview para descarga (funciona en producción sin DEBUG)."""
    title = ""

    def get(self, request, *args, **kwargs):
        import os
        filepath = os.path.join(
            settings.MEDIA_ROOT, "previews",
            f"solicitud_{self.base_request.uuid}.xlsx",
        )
        if not os.path.exists(filepath):
            raise Http404("El archivo Excel no existe. Genere la vista previa nuevamente.")
        return FileResponse(
            open(filepath, "rb"),
            as_attachment=True,
            filename=f"solicitud_{self.base_request.uuid}.xlsx",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


class OperacionSendView(
    OperationReadonlyViewMixin,
    View,
):
    # --- Atributos configurables ---
    title = ""  # no aplica, no renderiza un card

    def get(self, request, *args, **kwargs):
        operations = OperacionesService.get_all_operaciones(self.base_request)
        allow_empty = not operations and self.base_request.tipo_entrega == "Semanal"
        if not operations and not allow_empty:
            messages.error(request, "No hay operaciones para enviar.")
            return redirect(
                "operaciones:lista_operaciones", uuid=str(self.base_request.uuid)
            )

        # 1) Consultar estado SSN antes de enviar
        estado_ssn, datos_ssn, status_consulta = consultar_estado_ssn(
            self.base_request
        )

        if status_consulta >= 400:
            error_detail = datos_ssn.get('error') or datos_ssn.get('message', 'Error desconocido')
            msg = f"No se pudo verificar el estado en SSN: {error_detail}"
            messages.error(request, msg)
            return redirect(
                "operaciones:lista_operaciones", uuid=str(self.base_request.uuid)
            )

        # 2) Validar que el estado permita envío
        estados_bloqueados = [
            EstadoSSN.PRESENTADO,
            EstadoSSN.RECTIFICACION_PENDIENTE,
        ]

        if estado_ssn in estados_bloqueados:
            if estado_ssn == EstadoSSN.PRESENTADO:
                msg = "La entrega ya está PRESENTADA. Para modificarla, primero debe solicitar una rectificación."
            else:  # RECTIFICACION_PENDIENTE
                msg = "Hay una rectificación pendiente de aprobación. No se puede enviar hasta que la SSN la apruebe."

            messages.warning(request, msg)
            messages.info(request, f"Estado actual en SSN: {estado_ssn}")
            return redirect(
                "operaciones:lista_operaciones", uuid=str(self.base_request.uuid)
            )

        # 3) Enviar normalmente si el estado lo permite (VACÍO, CARGADO, A_RECTIFICAR)
        response_data, status, _ = enviar_y_guardar_solicitud(
            self.base_request, operations, allow_empty=allow_empty
        )
        if 200 <= status < 300:
            ssn_message = response_data.get("message", "Solicitud enviada correctamente.")
            messages.success(request, ssn_message)
            SessionService.clear_base_request(request)

            # Enviar email de confirmación (fire-and-forget — no bloquea la respuesta)
            try:
                from operaciones.services.email_service import PresentacionEmailService
                PresentacionEmailService.send_confirmacion(
                    self.base_request, operations, ssn_message=ssn_message
                )
            except Exception:
                logger.warning(
                    "No se pudo enviar email de confirmación para %s",
                    self.base_request.uuid,
                    exc_info=True,
                )

            # Ir al historial de respuestas de la solicitud:
            return redirect(
                "operaciones:solicitud_respuesta", uuid=str(self.base_request.uuid)
            )
        messages.error(
            request, response_data.get("message", "Error al enviar la solicitud.")
        )
        for err in response_data.get("errors", []):
            messages.error(request, err)
        # Mostrar historial de respuestas igual, para debugging:
        return redirect(
            "operaciones:solicitud_respuesta", uuid=str(self.base_request.uuid)
        )


class SolicitudRespuestasListView(
    StandaloneViewMixin,
    DetailView,
):
    # --- Atributos configurables ---
    model = BaseRequestModel
    pk_url_kwarg = "uuid"  # Cambiado de pk a uuid
    template_name = "lists/lista_respuestas_por_solicitud.html"
    context_object_name = "solicitud"
    title = "Detalle de Respuestas"
    header_buttons_config = ["back_solicitudes"]
    breadcrumbs = [
        ("Inicio", "theme:index"),
        ("Listado de Solicitudes", "operaciones:lista_solicitudes"),
        ("Detalle de Respuestas", None),
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["respuestas"] = [
            {
                "obj": resp,
                "formatted_payload": pretty_json(resp.payload_enviado),
                "formatted_response": pretty_json(resp.respuesta),
            }
            for resp in self.object.respuestas.all().order_by("created_at")
        ]
        return context


# =============================================================================
# VISTAS DE STOCKS MENSUALES
# =============================================================================


class MonthlyStockGenerateView(
    OperationEditViewMixin,
    TemplateView,
):
    """
    Vista para generar automáticamente los stocks mensuales a partir del
    stock del mes anterior y las operaciones semanales del mes.
    """

    # --- Atributos configurables ---
    template_name = "mensual/generar_stocks.html"
    title = "Generar Stocks Mensuales"
    header_buttons_config = ["back_operations"]
    breadcrumbs = [
        ("Inicio", "theme:index"),
        ("Solicitudes", "operaciones:lista_solicitudes"),
        (
            lambda self: f"Solicitud {self.base_request.uuid}",
            "operaciones:lista_operaciones",
            lambda self: {"uuid": self.base_request.uuid},
        ),
        ("Generar Stocks", None),
    ]

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        # Validar que sea solicitud mensual
        if self.base_request.tipo_entrega != TipoEntrega.MENSUAL:
            messages.error(
                request,
                "Esta función solo está disponible para solicitudes mensuales."
            )
            return redirect(
                "operaciones:lista_operaciones",
                uuid=self.base_request.uuid,
            )
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cronograma = self.base_request.cronograma

        # Información del mes anterior
        prev_request = MonthlyReportGeneratorService.get_previous_month_stock(cronograma)
        context["prev_request"] = prev_request
        context["prev_cronograma"] = MonthlyReportGeneratorService.get_previous_month_cronograma(cronograma)

        # Semanas del mes
        expected_weeks = MonthlyReportGeneratorService.get_weekly_cronogramas_for_month(cronograma)
        weekly_requests = MonthlyReportGeneratorService.get_weekly_requests_for_month(cronograma)
        missing_weeks = MonthlyReportGeneratorService.get_missing_weekly_requests(cronograma)

        context["expected_weeks"] = expected_weeks
        context["weekly_requests"] = weekly_requests
        context["missing_weeks"] = missing_weeks
        context["has_missing_weeks"] = bool(missing_weeks)

        # Stocks existentes
        existing_count = (
            self.base_request.stocks_inversion_mensuales.count()
            + self.base_request.stocks_plazofijo_mensuales.count()
            + self.base_request.stocks_chequespd_mensuales.count()
        )
        context["existing_stocks_count"] = existing_count
        context["can_generate"] = existing_count == 0

        return context

    def post(self, request, *args, **kwargs):
        """
        Genera los stocks mensuales.
        """
        # Acción de generar
        if "generate_action" in request.POST:
            result = MonthlyReportGeneratorService.generate_monthly_stocks(
                self.base_request
            )

            if result.success:
                messages.success(request, result.message)
                # Mostrar warnings si hay
                for warning in result.warnings:
                    messages.warning(request, warning)
                # Redirigir a la lista de operaciones
                return redirect(
                    "operaciones:lista_operaciones",
                    uuid=self.base_request.uuid,
                )
            else:
                messages.error(request, result.message)

        # Acción de eliminar stocks existentes
        elif "delete_stocks_action" in request.POST:
            count = MonthlyReportGeneratorService.delete_generated_stocks(
                self.base_request
            )
            if count > 0:
                messages.success(request, f"Se eliminaron {count} stocks.")
            else:
                messages.info(request, "No había stocks para eliminar.")

        return redirect(request.path)
