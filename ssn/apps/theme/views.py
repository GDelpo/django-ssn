from django.apps import apps
from django.conf import settings
from django.http import JsonResponse
from django.views.generic import TemplateView


def ssn_status(request):
    """
    Devuelve el estado de la conexión con la SSN en formato JSON.

    Solo accesible para usuarios autenticados. Si el token está por vencer
    o ya venció, intenta refrescarlo aquí mismo (idéntico a lo que haría
    cualquier llamada real a la API). Devuelve únicamente "ok" o "unavailable"
    para no exponer al usuario detalles internos del ciclo de vida del token.
    """
    if not request.user.is_authenticated:
        return JsonResponse({"status": "hidden"})

    try:
        ssn_client = apps.get_app_config("ssn_client").ssn_client
    except Exception:
        ssn_client = None

    if ssn_client is None:
        return JsonResponse({"status": "unavailable", "message": "Cliente SSN no inicializado"})

    # Si el token falta o está por vencer, refrescar ahora (igual que lo haría _check_token)
    if ssn_client._should_refresh_token():
        ssn_client._refresh_token()

    if ssn_client.token and not ssn_client._should_refresh_token():
        return JsonResponse({"status": "ok", "message": "Conectado"})

    return JsonResponse({"status": "unavailable", "message": "No se pudo conectar con SSN"})


class HomeView(TemplateView):
    """
    Vista principal para la página de inicio del sistema de operaciones financieras.
    """

    template_name = "home/index.html"
    title = "Inicio | Sistema de Operaciones SSN"

    # --- Métodos ---
    def get_title(self):
        return self.title

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Añadir el título al contexto
        context["title"] = self.get_title()

        # Definir los pasos del proceso
        context["pasos"] = [
            {
                "numero": 1,
                "titulo": "Crear Solicitud Base",
                "descripcion": "Inicie una nueva solicitud configurando el tipo de entrega y cronograma.",
                "icono": "fas fa-file-alt",
                "url": "operaciones:solicitud_base",
            },
            {
                "numero": 2,
                "titulo": "Agregar Operaciones",
                "descripcion": "Añada las operaciones financieras (compras, ventas, canjes o plazos fijos) a la solicitud.",
                "icono": "fas fa-plus-circle",
                "url": None,
            },
            {
                "numero": 3,
                "titulo": "Revisar Solicitud",
                "descripcion": "Verifique todas las operaciones antes de enviarlas a la SSN.",
                "icono": "fas fa-search",
                "url": None,
            },
            {
                "numero": 4,
                "titulo": "Enviar a SSN",
                "descripcion": "Transmita las operaciones validadas a la Superintendencia de Seguros de la Nación.",
                "icono": "fas fa-paper-plane",
                "url": None,
            },
        ]

        # Añadir correo de soporte desde settings
        context["support_email"] = settings.SUPPORT_EMAIL

        return context
