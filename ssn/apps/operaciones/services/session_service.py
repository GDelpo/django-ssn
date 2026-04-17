class SessionService:
    """
    Servicio para gestionar únicamente el UUID de la solicitud base (BaseRequest) en la sesión del usuario.

    Este servicio provee métodos estáticos para almacenar, recuperar y eliminar el UUID de la solicitud base.
    No almacena operaciones ni otro tipo de datos.
    """

    SESSION_KEY_BASE_REQUEST = "base_request_uuid"

    @staticmethod
    def set_base_request(request, base_request):
        """
        Almacena el UUID de una solicitud base en la sesión.

        Args:
            request (HttpRequest): Objeto request de Django.
            base_request (BaseRequestModel): Instancia de solicitud base a almacenar.
        """
        request.session[SessionService.SESSION_KEY_BASE_REQUEST] = str(
            base_request.uuid
        )
        request.session.modified = True

    @staticmethod
    def get_base_request_uuid(request):
        """
        Recupera el UUID de la solicitud base almacenada en la sesión.

        Args:
            request (HttpRequest): Objeto request de Django.

        Returns:
            str or None: UUID de la solicitud base, o None si no existe.
        """
        return request.session.get(SessionService.SESSION_KEY_BASE_REQUEST)

    @staticmethod
    def clear_base_request(request):
        """
        Elimina la referencia a la solicitud base de la sesión.

        Args:
            request (HttpRequest): Objeto request de Django.
        """
        request.session.pop(SessionService.SESSION_KEY_BASE_REQUEST, None)
