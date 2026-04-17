import logging
import time
from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Any, Callable, Dict, Optional, Tuple

import certifi
import jwt
import requests
from requests.exceptions import ConnectionError, ReadTimeout, RequestException, Timeout

# Configuración del logger para registrar eventos e información relevante.
logger = logging.getLogger("ssn_client")


# Definición de la metaclase Singleton
class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class SsnService(metaclass=Singleton):
    """
    Servicio para autenticarse, manejar tokens de sesión y realizar solicitudes HTTP (GET y POST)
    a una API determinada. Gestiona la renovación del token cuando ha expirado o es inválido,
    y reintenta solicitudes en caso de errores o fallos temporales.
    """

    def __init__(
        self,
        username: str,
        password: str,
        cia: str,
        base_url: str,
        max_retries: int = 3,
        retry_delay: int = 2,
        token_refresh_margin: int = 300,  # 5 minutos en segundos
        verify_ssl: bool = True,  # Verificación SSL (False para entornos de test con cert self-signed)
        request_timeout: Tuple[int, int] = (10, 20),  # (connect_timeout, read_timeout) en segundos
    ) -> None:
        # Evita re-inicializar la instancia si ya fue creada.
        if hasattr(self, "_initialized") and self._initialized:
            return
        # Inicialización de atributos con los datos proporcionados.
        self.username = username
        self.password = password
        self.cia = cia
        self.base_url = base_url
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.token_refresh_margin = token_refresh_margin
        self.verify_ssl = certifi.where() if verify_ssl else False
        self.request_timeout = request_timeout
        self.session = requests.Session()
        # Se intenta obtener el token de autenticación al instanciar el servicio.
        self.token = self._get_token()
        self._initialized = True  # Marca que ya fue inicializado

    def _get_token(self) -> Optional[str]:
        """
        Realiza una solicitud POST a la ruta de login para obtener el token de autenticación.

        Returns:
            Optional[str]: Token JWT o None si no se pudo obtener
        """
        headers = {"Content-Type": "application/json"}
        # Datos necesarios para la autenticación.
        data = {"user": self.username, "cia": self.cia, "password": self.password}
        token_url = f"{self.base_url}/login"
        try:
            response = self.session.post(
                token_url, json=data, headers=headers,
                verify=self.verify_ssl, timeout=self.request_timeout,
            )
            if response.status_code == HTTPStatus.OK:
                token = response.json().get("token")
                logger.debug("Token obtenido exitosamente.")
                return token
            logger.error(
                f"Error obteniendo token: {response.status_code} - {response.text}"
            )
        except Timeout as timeout_err:
            logger.error(f"Timeout al solicitar token de SSN ({self.request_timeout}s): {timeout_err}")
        except ConnectionError as conn_err:
            logger.error(f"Error de conexión al solicitar token de SSN: {conn_err}")
        except RequestException as req_err:
            logger.error(f"Excepción en la solicitud de token: {req_err}")
        except Exception as e:
            logger.error(f"Excepción inesperada al obtener token: {e}")
        return None

    def _get_expiration_date(self) -> Optional[datetime]:
        """
        Decodifica el JWT y extrae la fecha de expiración a partir del campo 'exp'.

        Returns:
            Optional[datetime]: Fecha de expiración del token o None si no se pudo decodificar
        """
        if not self.token:
            return None

        try:
            # Decodificar sin verificar la firma solo para extraer el payload
            payload = jwt.decode(self.token, options={"verify_signature": False})
            exp_timestamp = payload.get("exp")
            if exp_timestamp:
                return datetime.fromtimestamp(exp_timestamp)
            else:
                logger.warning("El token no contiene el campo 'exp'.")
                return None
        except Exception as e:
            logger.error(f"Error al decodificar el token: {e}")
            return None

    def _should_refresh_token(self) -> bool:
        """
        Determina si el token debe ser refrescado basado en su fecha de expiración.

        Returns:
            bool: True si el token debe ser refrescado, False en caso contrario
        """
        if not self.token:
            return True

        expiration_date = self._get_expiration_date()
        if not expiration_date:
            return True

        # Refrescar el token si está a punto de expirar (dentro del margen)
        refresh_threshold = datetime.now() + timedelta(
            seconds=self.token_refresh_margin
        )
        return refresh_threshold >= expiration_date

    def _refresh_token(self) -> bool:
        """
        Refresca el token de autenticación.

        Returns:
            bool: True si se refrescó exitosamente, False en caso contrario
        """
        logger.info("Refrescando token...")
        new_token = self._get_token()
        if new_token:
            self.token = new_token
            logger.info("Token refrescado exitosamente.")
            return True
        logger.error("Fallo al refrescar el token.")
        return False

    def _check_token(self) -> bool:
        """
        Verifica si existe un token válido y, de lo contrario, lo renueva.

        Returns:
            bool: True si el token es válido, False en caso contrario
        """
        if not self.token:
            logger.debug("No hay token. Obteniendo uno nuevo...")
            return self._refresh_token()

        if self._should_refresh_token():
            logger.debug("El token está por expirar. Refrescando...")
            return self._refresh_token()

        logger.debug("Token válido.")
        return True

    def _get_headers(self) -> Dict[str, str]:
        """
        Construye los encabezados necesarios para las solicitudes, incluyendo el token.

        Returns:
            Dict[str, str]: Encabezados HTTP para las solicitudes
        """
        return {
            "Token": self.token or "",
            "Content-Type": "application/json",
        }

    def _make_request(
        self,
        request_func: Callable[..., requests.Response],
        url: str,
        **kwargs: Any,
    ) -> Tuple[Optional[Dict[str, Any]], int]:
        """
        Método genérico para realizar solicitudes GET o POST con reintentos, verificación
        del token y refresco en caso de recibir un 401 (no autorizado).

        Args:
            request_func: Función a usar para la solicitud (session.get, session.post, etc.)
            url: URL a la que realizar la solicitud
            **kwargs: Argumentos adicionales para la función de solicitud

        Returns:
            Tuple[Optional[Dict[str, Any]], int]: Tupla con (datos de respuesta, código de estado HTTP)
        """
        if not self._check_token():
            logger.error("Fallo en la verificación del token. Abortando solicitud.")
            return {"error": "Error de autenticación"}, HTTPStatus.UNAUTHORIZED

        kwargs["headers"] = self._get_headers()

        for attempt in range(1, self.max_retries + 1):
            # Log detallado de la solicitud antes de enviarla
            method_name = request_func.__name__.upper()
            logger.info(f"ENVIANDO {method_name} a {url} (intento {attempt})")

            # Loggear headers sin el token completo (por seguridad)
            safe_headers = self._get_safe_headers(kwargs.get("headers", {}))
            logger.debug(f"Headers: {safe_headers}")

            # Loggear el payload (json o params)
            self._log_request_payload(kwargs)

            try:
                response = request_func(url, **kwargs, verify=self.verify_ssl, timeout=self.request_timeout)
                status_code = response.status_code

                # Loggear la respuesta
                logger.debug(
                    f"Respuesta status code: {status_code} ({HTTPStatus(status_code).phrase})"
                )
                logger.debug(f"Respuesta headers: {dict(response.headers)}")

                # Intentar capturar el contenido de la respuesta para debugging
                response_data = self._parse_response(response)

                if status_code == HTTPStatus.UNAUTHORIZED:
                    if self._handle_unauthorized(kwargs):
                        # Reintentar con token nuevo
                        response = request_func(url, **kwargs, verify=self.verify_ssl, timeout=self.request_timeout)
                        status_code = response.status_code
                        response_data = self._parse_response(response)
                    else:
                        return {
                            "error": "Error de autenticación"
                        }, HTTPStatus.UNAUTHORIZED

                if self._is_success_status(status_code):
                    logger.info(f"Solicitud exitosa a {url} ({status_code})")
                    return response_data, status_code
                else:
                    # Para respuestas de error, log pero también devolver el status code
                    logger.error(
                        f"Error en la respuesta: Status {status_code} ({HTTPStatus(status_code).phrase}), "
                        f"Contenido: {response_data}"
                    )
                    return response_data, status_code

            except Timeout as timeout_err:
                logger.error(
                    f"Timeout en la solicitud a {url} (intento {attempt}/{self.max_retries}, "
                    f"timeout={self.request_timeout}s): {timeout_err}"
                )
            except ConnectionError as conn_err:
                logger.error(f"Error de conexión a {url} (intento {attempt}/{self.max_retries}): {conn_err}")
            except RequestException as req_err:
                logger.error(f"Excepción en la solicitud a {url}: {req_err}")
            except Exception as e:
                logger.error(
                    f"Excepción inesperada en la solicitud a {url}: {e}", exc_info=True
                )

            if attempt < self.max_retries:
                backoff_delay = self.retry_delay * (2 ** (attempt - 1))
                logger.info(f"Reintentando en {backoff_delay} segundos...")
                time.sleep(backoff_delay)

        logger.error(f"Se agotaron los {self.max_retries} reintentos para {url}")
        return {
            "error": f"Se agotaron los {self.max_retries} reintentos para {url}"
        }, HTTPStatus.SERVICE_UNAVAILABLE

    def _get_safe_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """
        Genera una copia segura de los headers, ocultando información sensible.

        Args:
            headers: Headers originales

        Returns:
            Dict[str, str]: Headers seguros para logging
        """
        safe_headers = dict(headers)
        if "Token" in safe_headers and safe_headers["Token"]:
            token_part = (
                safe_headers["Token"][:10] + "..."
                if len(safe_headers["Token"]) > 10
                else "***"
            )
            safe_headers["Token"] = token_part
        return safe_headers

    def _log_request_payload(self, kwargs: Dict[str, Any]) -> None:
        """
        Registra el payload de la solicitud en el log.

        Args:
            kwargs: Argumentos de la solicitud
        """
        if "json" in kwargs:
            logger.debug(f"Payload JSON: {kwargs['json']}")
        if "params" in kwargs:
            logger.debug(f"Params: {kwargs['params']}")
        if "data" in kwargs:
            logger.debug(f"Data: {kwargs['data']}")

    def _parse_response(self, response: requests.Response) -> Dict[str, Any]:
        """
        Parsea la respuesta HTTP a un diccionario.

        Args:
            response: Respuesta HTTP

        Returns:
            Dict[str, Any]: Datos de la respuesta como diccionario
        """
        try:
            return response.json()
        except Exception:
            # Si no es JSON, usar el texto como mensaje de error
            return {"error": response.text[:1000] if response.text else "Sin contenido"}

    def _handle_unauthorized(self, kwargs: Dict[str, Any]) -> bool:
        """
        Maneja una respuesta 401 Unauthorized refrescando el token.

        Args:
            kwargs: Argumentos de la solicitud para actualizar los headers

        Returns:
            bool: True si se pudo refrescar el token, False en caso contrario
        """
        logger.warning("Recibido 401. Refrescando token e intentando nuevamente...")
        if self._refresh_token():
            kwargs["headers"] = self._get_headers()

            # Loggear nuevamente con el token actualizado
            logger.debug("Reintentando con token actualizado")
            safe_headers = self._get_safe_headers(kwargs["headers"])
            logger.debug(f"Headers actualizados: {safe_headers}")
            return True
        return False

    def _is_success_status(self, status_code: int) -> bool:
        """
        Determina si un código de estado HTTP indica éxito.

        Args:
            status_code: Código de estado HTTP

        Returns:
            bool: True si es un código de éxito (2xx), False en caso contrario
        """
        return 200 <= status_code < 300

    def get_resource(
        self, resource: str, params: Optional[Dict[str, Any]] = None
    ) -> Tuple[Dict[str, Any], int]:
        """
        Realiza una solicitud GET para obtener un recurso específico.

        Args:
            resource: Nombre del recurso
            params: Parámetros de consulta

        Returns:
            Tuple[Dict[str, Any], int]: Tupla con (datos de respuesta, código de estado HTTP)
        """
        url = f"{self.base_url}/inv/{resource}"
        result, status_code = self._make_request(self.session.get, url, params=params)
        if result is None:
            logger.error(f"Fallo al obtener el recurso: {resource}")
            result = {"error": f"No se pudo obtener el recurso {resource}"}
        return result, status_code

    def post_resource(
        self, resource: str, data: Optional[Dict[str, Any]] = None
    ) -> Tuple[Dict[str, Any], int]:
        """
        Realiza una solicitud POST para enviar datos a un recurso específico.

        Args:
            resource: Nombre del recurso
            data: Datos a enviar

        Returns:
            Tuple[Dict[str, Any], int]: Tupla con (datos de respuesta, código de estado HTTP)
        """
        url = f"{self.base_url}/inv/{resource}"
        result, status_code = self._make_request(self.session.post, url, json=data)
        if result is None:
            logger.error(f"Fallo al enviar POST al recurso: {resource}")
            result = {"error": f"No se pudo enviar datos al recurso {resource}"}
        return result, status_code

    def put_resource(
        self, resource: str, data: Optional[Dict[str, Any]] = None
    ) -> Tuple[Dict[str, Any], int]:
        """
        Realiza una solicitud PUT para actualizar datos en un recurso específico.

        Args:
            resource: Nombre del recurso
            data: Datos a enviar para la actualización

        Returns:
            Tuple[Dict[str, Any], int]: Tupla con (datos de respuesta, código de estado HTTP)
        """
        url = f"{self.base_url}/inv/{resource}"
        # La única diferencia clave es usar self.session.put
        result, status_code = self._make_request(self.session.put, url, json=data)
        if result is None:
            logger.error(f"Fallo al enviar PUT al recurso: {resource}")
            result = {"error": f"No se pudo actualizar datos en el recurso {resource}"}
        return result, status_code
