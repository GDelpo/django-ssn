"""
Servicio centralizado de validaciones para solicitudes.

Este módulo contiene toda la lógica de validación de solicitudes,
incluyendo validaciones de cronograma, estado SSN, y reglas de negocio.
"""
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.conf import settings

from ssn_client.services import consultar_estado_ssn, EstadoSSN

if TYPE_CHECKING:
    from ..models import BaseRequestModel

logger = logging.getLogger("operaciones")


@dataclass
class ValidationResult:
    """Resultado de una validación."""
    is_valid: bool
    error_message: str | None = None
    field_name: str | None = None  # Campo específico donde mostrar el error
    warning_message: str | None = None  # Advertencia no bloqueante para el usuario


class SolicitudValidationService:
    """
    Servicio centralizado de validaciones para solicitudes.
    
    Agrupa todas las validaciones de negocio relacionadas con la creación
    y modificación de solicitudes.
    """

    # =========================================================================
    # VALIDACIÓN DE DUPLICADOS
    # =========================================================================
    
    @staticmethod
    def validate_no_duplicate(
        cronograma: str,
        tipo_entrega: str,
        exclude_pk: int | None = None
    ) -> ValidationResult:
        """
        Valida que no exista una solicitud duplicada para el mismo cronograma y tipo.
        
        Args:
            cronograma: El cronograma a validar (ej: '2026-03' o '2026-10')
            tipo_entrega: 'Semanal' o 'Mensual'
            exclude_pk: PK a excluir (para ediciones)
            
        Returns:
            ValidationResult con el resultado de la validación
        """
        from ..models import BaseRequestModel
        
        qs = BaseRequestModel.objects.filter(
            cronograma=cronograma, tipo_entrega=tipo_entrega
        )
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
            
        if qs.exists():
            field_name = "cronograma_mensual" if tipo_entrega == "Mensual" else "cronograma_semanal"
            return ValidationResult(
                is_valid=False,
                error_message=f"Ya existe una solicitud {tipo_entrega.lower()} para este cronograma.",
                field_name=field_name,
            )
        
        return ValidationResult(is_valid=True)

    # =========================================================================
    # VALIDACIÓN DE CRONOGRAMA ANTERIOR
    # =========================================================================
    
    @staticmethod
    def get_previous_cronograma(cronograma: str, tipo_entrega: str) -> str | None:
        """
        Calcula el cronograma anterior según el tipo de entrega.
        
        Para Mensual: '2026-03' -> '2026-02'
        Para Semanal: '2026-10' -> '2026-09'
        
        Args:
            cronograma: Cronograma actual
            tipo_entrega: 'Semanal' o 'Mensual'
            
        Returns:
            El cronograma anterior, o None si es el primero del año
        """
        try:
            year, num = map(int, cronograma.split("-"))
            
            if tipo_entrega == "Mensual":
                if num == 1:
                    return f"{year - 1}-12"
                return f"{year}-{num - 1:02d}"
            else:  # Semanal
                if num == 1:
                    # Primera semana del año - no validamos
                    return None
                return f"{year}-{num - 1:02d}"
        except (ValueError, AttributeError):
            logger.warning(f"No se pudo parsear el cronograma: {cronograma}")
            return None

    @staticmethod
    def validate_previous_cronograma_sent(
        cronograma: str,
        tipo_entrega: str
    ) -> ValidationResult:
        """
        Valida que el cronograma anterior haya sido PRESENTADO.
        
        Reglas:
        - Si existe solicitud anterior y NO está PRESENTADA -> Error
        - Si NO existe solicitud anterior (saltando cronogramas) -> Error
        - Excepción: Si no hay NINGUNA solicitud del tipo, permite crear la primera
        
        Args:
            cronograma: El cronograma a crear
            tipo_entrega: 'Semanal' o 'Mensual'
            
        Returns:
            ValidationResult con el resultado de la validación
        """
        from ..models import BaseRequestModel
        from ..models.choices import EstadoSolicitud
        
        prev_cronograma = SolicitudValidationService.get_previous_cronograma(
            cronograma, tipo_entrega
        )
        
        if not prev_cronograma:
            # Es el primer cronograma del año, permitir
            return ValidationResult(is_valid=True)
        
        # Verificar si existe alguna solicitud de este tipo
        any_exists = BaseRequestModel.objects.filter(tipo_entrega=tipo_entrega).exists()
        
        if not any_exists:
            # No hay ninguna solicitud de este tipo, permitir crear la primera
            # (independientemente del cronograma)
            return ValidationResult(is_valid=True)
        
        # Buscar la solicitud del cronograma anterior
        prev_request = BaseRequestModel.objects.filter(
            cronograma=prev_cronograma, tipo_entrega=tipo_entrega
        ).first()
        
        field_name = "cronograma_mensual" if tipo_entrega == "Mensual" else "cronograma_semanal"
        
        if not prev_request:
            # No existe el cronograma anterior -> te estás saltando períodos
            # Buscar el último cronograma existente para dar mejor mensaje
            last_request = BaseRequestModel.objects.filter(
                tipo_entrega=tipo_entrega
            ).order_by('-cronograma').first()
            
            if last_request:
                return ValidationResult(
                    is_valid=False,
                    error_message=(
                        f"No puede crear el cronograma {cronograma} porque está saltando períodos. "
                        f"El último cronograma existente es {last_request.cronograma}. "
                        f"Debe crear los cronogramas en orden."
                    ),
                    field_name=field_name,
                )
        
        if prev_request and prev_request.estado != EstadoSolicitud.PRESENTADO:
            return ValidationResult(
                is_valid=False,
                error_message=(
                    f"No puede crear este cronograma porque el anterior ({prev_cronograma}) "
                    f"no ha sido enviado. Estado actual: {prev_request.get_estado_display()}."
                ),
                field_name=field_name,
            )
        
        return ValidationResult(is_valid=True)

    # =========================================================================
    # VALIDACIÓN CONTRA SSN
    # =========================================================================
    
    @staticmethod
    def validate_ssn_status(
        cronograma: str,
        tipo_entrega: str
    ) -> ValidationResult:
        """
        Valida el estado del cronograma en la SSN.
        
        Verifica que el cronograma no esté ya PRESENTADO o en proceso
        de rectificación en la SSN.
        
        Args:
            cronograma: El cronograma a validar
            tipo_entrega: 'Semanal' o 'Mensual'
            
        Returns:
            ValidationResult con el resultado de la validación
        """
        from ..models import BaseRequestModel
        
        try:
            # Crear objeto temporal para consultar
            temp_request = BaseRequestModel(
                tipo_entrega=tipo_entrega,
                cronograma=cronograma,
                codigo_compania=settings.SSN_API_CIA,
            )
            
            estado_ssn, response, status = consultar_estado_ssn(temp_request)
            logger.info(f"Validación SSN para {cronograma} ({tipo_entrega}): estado={estado_ssn}, status={status}")
            
            # Si no se pudo obtener el estado (error de conexión, timeout, etc.)
            if estado_ssn is None:
                logger.warning(f"No se pudo obtener estado SSN para {cronograma}: status={status}, response={response}")
                return ValidationResult(
                    is_valid=False,
                    error_message=(
                        "No se pudo verificar el estado en la SSN (servicio no disponible). "
                        "Intente nuevamente en unos minutos."
                    ),
                )
            
            estado_ssn_upper = estado_ssn.upper() if estado_ssn else ""
            field_name = "cronograma_mensual" if tipo_entrega == "Mensual" else "cronograma_semanal"
            
            if estado_ssn_upper == EstadoSSN.PRESENTADO.upper():
                return ValidationResult(
                    is_valid=False,
                    error_message=(
                        "Este cronograma ya fue presentado en la SSN. "
                        "Si necesita modificarlo, debe solicitar una rectificación."
                    ),
                    field_name=field_name,
                )
            
            if estado_ssn_upper in [
                EstadoSSN.RECTIFICACION_PENDIENTE.upper(),
                EstadoSSN.A_RECTIFICAR.upper()
            ]:
                return ValidationResult(
                    is_valid=False,
                    error_message=(
                        f"Este cronograma tiene una rectificación pendiente en la SSN "
                        f"(estado: {estado_ssn}). Debe esperar a que se procese."
                    ),
                    field_name=field_name,
                )
            
            return ValidationResult(is_valid=True)
            
        except Exception as e:
            logger.error(f"Error al consultar SSN para {cronograma}: {str(e)}")
            return ValidationResult(
                is_valid=False,
                error_message=(
                    "No se pudo verificar el estado en la SSN (servicio no disponible). "
                    "Intente nuevamente en unos minutos."
                ),
            )

    # =========================================================================
    # VALIDACIÓN DE MENSUAL (DATOS NECESARIOS)
    # =========================================================================
    
    @staticmethod
    def validate_monthly_has_data(cronograma: str) -> ValidationResult:
        """
        Valida que existan datos para generar el stock mensual.
        
        Para crear una solicitud mensual se necesita:
        - Stock del mes anterior, O
        - Operaciones semanales del período
        
        Args:
            cronograma: El cronograma mensual a validar
            
        Returns:
            ValidationResult con el resultado de la validación
        """
        from .monthly_report_service import MonthlyReportGeneratorService
        
        prev_request = MonthlyReportGeneratorService.get_previous_month_stock(cronograma)
        weekly_requests = MonthlyReportGeneratorService.get_weekly_requests_for_month(cronograma)
        
        if not prev_request and weekly_requests.count() == 0:
            return ValidationResult(
                is_valid=False,
                error_message=(
                    f"No se puede crear la solicitud mensual {cronograma}: "
                    "no existe stock del mes anterior ni operaciones semanales del período."
                ),
                field_name="cronograma_mensual",
            )
        
        return ValidationResult(is_valid=True)

    # =========================================================================
    # VALIDACIÓN COMPLETA
    # =========================================================================
    
    @classmethod
    def validate_new_solicitud(
        cls,
        cronograma: str,
        tipo_entrega: str,
        exclude_pk: int | None = None,
        skip_ssn: bool = False
    ) -> tuple[list[ValidationResult], list[str]]:
        """
        Ejecuta todas las validaciones necesarias para crear una solicitud.
        
        Args:
            cronograma: El cronograma a validar
            tipo_entrega: 'Semanal' o 'Mensual'
            exclude_pk: PK a excluir de validación de duplicados
            skip_ssn: Si es True, omite la validación contra SSN
            
        Returns:
            Tupla (errores, advertencias):
            - errores: Lista de ValidationResult con errores (vacía si todo es válido)
            - advertencias: Lista de strings con mensajes de advertencia no bloqueantes
        """
        errors = []
        warnings = []
        
        # 1. Validar duplicados
        result = cls.validate_no_duplicate(cronograma, tipo_entrega, exclude_pk)
        if not result.is_valid:
            errors.append(result)
            return errors, warnings  # Si hay duplicado, no tiene sentido seguir validando
        
        # 2. Validar cronograma anterior enviado
        result = cls.validate_previous_cronograma_sent(cronograma, tipo_entrega)
        if not result.is_valid:
            errors.append(result)
        
        # 3. Validar contra SSN (solo si no hay errores previos)
        if not errors and not skip_ssn:
            result = cls.validate_ssn_status(cronograma, tipo_entrega)
            if not result.is_valid:
                errors.append(result)
            elif result.warning_message:
                warnings.append(result.warning_message)
        
        # 4. Validaciones específicas para mensual
        if tipo_entrega == "Mensual" and not errors:
            result = cls.validate_monthly_has_data(cronograma)
            if not result.is_valid:
                errors.append(result)
        
        return errors, warnings
