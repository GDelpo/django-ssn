"""
Servicio de alertas y notificaciones para vencimientos de presentaciones SSN.

Reglas de vencimiento:
- Semanal: Debe presentarse antes de que termine la semana siguiente
- Mensual: Debe presentarse hasta el 5to día hábil del mes siguiente
"""

import datetime
import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from django.core.cache import caches
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger("operaciones")


class AlertLevel(Enum):
    """Niveles de severidad de las alertas."""
    INFO = "info"
    WARNING = "warning"
    DANGER = "danger"
    SUCCESS = "success"


class AlertType(Enum):
    """Tipos de alerta."""
    SEMANAL_PENDIENTE = "semanal_pendiente"
    SEMANAL_VENCIDO = "semanal_vencido"
    MENSUAL_PENDIENTE = "mensual_pendiente"
    MENSUAL_PROXIMO_VENCER = "mensual_proximo_vencer"
    MENSUAL_VENCIDO = "mensual_vencido"


@dataclass
class Alert:
    """Representa una alerta/notificación."""
    level: AlertLevel
    alert_type: AlertType
    title: str
    message: str
    cronograma: str
    fecha_vencimiento: Optional[datetime.date] = None
    dias_restantes: Optional[int] = None
    url: Optional[str] = None
    button_label: str = "Ir a cargar"

    @property
    def icon(self) -> str:
        """Retorna el ícono SVG según el nivel."""
        icons = {
            AlertLevel.INFO: """<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"/></svg>""",
            AlertLevel.WARNING: """<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/></svg>""",
            AlertLevel.DANGER: """<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/></svg>""",
            AlertLevel.SUCCESS: """<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/></svg>""",
        }
        return icons.get(self.level, icons[AlertLevel.INFO])

    @property
    def css_classes(self) -> str:
        """Retorna las clases CSS según el nivel."""
        classes = {
            AlertLevel.INFO: "bg-blue-50 border-blue-400 text-blue-800",
            AlertLevel.WARNING: "bg-yellow-50 border-yellow-400 text-yellow-800",
            AlertLevel.DANGER: "bg-red-50 border-red-400 text-red-800",
            AlertLevel.SUCCESS: "bg-green-50 border-green-400 text-green-800",
        }
        return classes.get(self.level, classes[AlertLevel.INFO])


# Importar funciones de días hábiles desde date_utils
from operaciones.helpers.date_utils import (
    FERIADOS_FIJOS,
    FERIADOS_MOVILES,
    es_feriado,
    es_dia_habil,
    calcular_quinto_dia_habil,
)


def dias_hasta_fecha(fecha_objetivo: datetime.date) -> int:
    """
    Calcula los días restantes hasta una fecha.
    
    Args:
        fecha_objetivo: Fecha hasta la cual calcular
        
    Returns:
        Número de días (negativo si ya pasó)
    """
    hoy = datetime.date.today()
    return (fecha_objetivo - hoy).days


# =============================================================================
# Caché cross-process para alertas
# =============================================================================

_ALERTS_CACHE_KEY = "ssn_pending_alerts_v1"
_ALERTS_CACHE_TTL = 6 * 60 * 60  # 6 horas


# =============================================================================
# Servicio principal de alertas
# =============================================================================

class AlertService:
    """Servicio para generar alertas de vencimientos."""
    
    @staticmethod
    def get_alertas_pendientes() -> List[Alert]:
        """
        Consulta DB y retorna todas las alertas pendientes ordenadas por urgencia.
        No usa caché — es la fuente de verdad. Preferir get_cached_alerts() en el
        context processor para evitar una query por cada request autenticado.
        """
        alertas = []

        # Alertas semanales
        alertas.extend(AlertService._get_alertas_semanales())

        # Alertas mensuales
        alertas.extend(AlertService._get_alertas_mensuales())

        # Ordenar por urgencia (danger > warning > info)
        orden_nivel = {
            AlertLevel.DANGER: 0,
            AlertLevel.WARNING: 1,
            AlertLevel.INFO: 2,
            AlertLevel.SUCCESS: 3,
        }
        alertas.sort(key=lambda a: (orden_nivel.get(a.level, 99), a.dias_restantes or 0))

        return alertas

    @staticmethod
    def refresh_alerts() -> List[Alert]:
        """
        Recomputa alertas desde la DB y las guarda en la caché cross-process.
        Llamar desde el cron (management command send_deadline_alerts).
        """
        alertas = AlertService.get_alertas_pendientes()
        try:
            caches["alerts"].set(_ALERTS_CACHE_KEY, alertas, _ALERTS_CACHE_TTL)
        except Exception:
            logger.warning("No se pudo guardar alertas en caché", exc_info=True)
        return alertas

    @staticmethod
    def get_cached_alerts() -> List[Alert]:
        """
        Retorna alertas desde caché. Si la caché está vacía, refresca desde DB.
        Llamar desde el context processor — nunca toca la DB si ya corrió el cron.
        """
        try:
            alertas = caches["alerts"].get(_ALERTS_CACHE_KEY)
        except Exception:
            alertas = None
        if alertas is None:
            alertas = AlertService.refresh_alerts()
        return alertas
    
    @staticmethod
    def _get_alertas_semanales() -> List[Alert]:
        """Genera alertas para presentaciones semanales pendientes."""
        from operaciones.models import BaseRequestModel, TipoEntrega, EstadoSolicitud
        from operaciones.helpers.date_utils import generate_week_options_with_overlap
        
        alertas = []
        hoy = datetime.date.today()
        año_actual = hoy.year
        
        # Obtener semanas disponibles
        semanas = generate_week_options_with_overlap(año_actual)
        
        for week_id, date_range in semanas:
            # Parsear fechas de la semana
            try:
                start_str, end_str = date_range.split(" - ")
                end_date = datetime.datetime.strptime(end_str.strip(), "%d/%m/%Y").date()
            except (ValueError, AttributeError):
                continue
            
            # Fecha límite: fin de la semana siguiente (7 días después del fin de la semana)
            fecha_limite = end_date + datetime.timedelta(days=7)
            
            # Solo considerar semanas ya cerradas (end_date en el pasado)
            if end_date >= hoy:
                continue
            
            # Verificar si ya existe presentación en estado final (suprime la alerta)
            existe_presentacion = BaseRequestModel.objects.filter(
                cronograma=week_id,
                tipo_entrega=TipoEntrega.SEMANAL,
                estado__in=[
                    EstadoSolicitud.PRESENTADO,
                    EstadoSolicitud.CARGADO,
                    EstadoSolicitud.RECTIFICACION_PENDIENTE,
                ]
            ).exists()

            if existe_presentacion:
                continue

            # Verificar si hay un borrador existente → apuntar a él en vez de crear uno nuevo
            borrador = BaseRequestModel.objects.filter(
                cronograma=week_id,
                tipo_entrega=TipoEntrega.SEMANAL,
                estado__in=[EstadoSolicitud.BORRADOR, EstadoSolicitud.A_RECTIFICAR],
            ).first()

            if borrador:
                url_alerta = reverse('operaciones:lista_operaciones', kwargs={'uuid': str(borrador.uuid)})
                button_label = "Continuar carga" if borrador.estado == EstadoSolicitud.BORRADOR else "Continuar rectificación"
            else:
                url_alerta = f"{reverse('operaciones:solicitud_base')}?tipo_entrega=Semanal&cronograma={week_id}"
                button_label = "Ir a cargar"

            # Calcular días restantes
            dias_restantes = dias_hasta_fecha(fecha_limite)

            if dias_restantes < 0:
                # Ya venció
                alertas.append(Alert(
                    level=AlertLevel.DANGER,
                    alert_type=AlertType.SEMANAL_VENCIDO,
                    title="Presentación Semanal Vencida",
                    message=f"La semana {week_id} ({date_range}) debió presentarse antes del {fecha_limite.strftime('%d/%m/%Y')}.",
                    cronograma=week_id,
                    fecha_vencimiento=fecha_limite,
                    dias_restantes=dias_restantes,
                    url=url_alerta,
                    button_label=button_label,
                ))
            elif dias_restantes <= 3:
                # Próximo a vencer
                alertas.append(Alert(
                    level=AlertLevel.WARNING,
                    alert_type=AlertType.SEMANAL_PENDIENTE,
                    title="Presentación Semanal Pendiente",
                    message=f"La semana {week_id} debe presentarse antes del {fecha_limite.strftime('%d/%m/%Y')} ({dias_restantes} días restantes).",
                    cronograma=week_id,
                    fecha_vencimiento=fecha_limite,
                    dias_restantes=dias_restantes,
                    url=url_alerta,
                    button_label=button_label,
                ))
            else:
                # Pendiente pero con tiempo
                alertas.append(Alert(
                    level=AlertLevel.INFO,
                    alert_type=AlertType.SEMANAL_PENDIENTE,
                    title="Presentación Semanal Pendiente",
                    message=f"La semana {week_id} está pendiente de presentación (vence el {fecha_limite.strftime('%d/%m/%Y')}).",
                    cronograma=week_id,
                    fecha_vencimiento=fecha_limite,
                    dias_restantes=dias_restantes,
                    url=url_alerta,
                    button_label=button_label,
                ))
        
        return alertas
    
    @staticmethod
    def _get_alertas_mensuales() -> List[Alert]:
        """Genera alertas para presentaciones mensuales pendientes."""
        from operaciones.models import BaseRequestModel, TipoEntrega, EstadoSolicitud
        
        alertas = []
        hoy = datetime.date.today()
        
        # Verificar los últimos 3 meses
        for i in range(3):
            # Calcular el mes a verificar
            fecha_check = hoy - datetime.timedelta(days=30 * (i + 1))
            año_check = fecha_check.year
            mes_check = fecha_check.month
            
            # El cronograma mensual
            cronograma = f"{año_check}-{mes_check:02d}"
            
            # Calcular fecha límite (5to día hábil del mes siguiente)
            if mes_check == 12:
                año_limite = año_check + 1
                mes_limite = 1
            else:
                año_limite = año_check
                mes_limite = mes_check + 1
            
            fecha_limite = calcular_quinto_dia_habil(año_limite, mes_limite)
            
            # Nombre del mes para mostrar
            meses = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
            nombre_mes = f"{meses[mes_check]} {año_check}"
            
            # Verificar si ya existe presentación en estado final (suprime la alerta)
            existe_presentacion = BaseRequestModel.objects.filter(
                cronograma=cronograma,
                tipo_entrega=TipoEntrega.MENSUAL,
                estado__in=[
                    EstadoSolicitud.PRESENTADO,
                    EstadoSolicitud.CARGADO,
                    EstadoSolicitud.RECTIFICACION_PENDIENTE,
                ]
            ).exists()

            if existe_presentacion:
                continue

            # Solo alertar si ya pasó el mes
            if hoy.year < año_limite or (hoy.year == año_limite and hoy.month < mes_limite):
                continue

            # Verificar si hay un borrador existente → apuntar a él en vez de crear uno nuevo
            borrador = BaseRequestModel.objects.filter(
                cronograma=cronograma,
                tipo_entrega=TipoEntrega.MENSUAL,
                estado__in=[EstadoSolicitud.BORRADOR, EstadoSolicitud.A_RECTIFICAR],
            ).first()

            if borrador:
                url_alerta = reverse('operaciones:lista_operaciones', kwargs={'uuid': str(borrador.uuid)})
                button_label = "Continuar carga" if borrador.estado == EstadoSolicitud.BORRADOR else "Continuar rectificación"
            else:
                url_alerta = f"{reverse('operaciones:solicitud_base')}?tipo_entrega=Mensual&cronograma={cronograma}"
                button_label = "Ir a cargar"

            # Calcular días restantes
            dias_restantes = dias_hasta_fecha(fecha_limite)

            if dias_restantes < 0:
                # Ya venció
                alertas.append(Alert(
                    level=AlertLevel.DANGER,
                    alert_type=AlertType.MENSUAL_VENCIDO,
                    title="Presentación Mensual Vencida",
                    message=f"El período {nombre_mes} debió presentarse antes del {fecha_limite.strftime('%d/%m/%Y')} (5° día hábil).",
                    cronograma=cronograma,
                    fecha_vencimiento=fecha_limite,
                    dias_restantes=dias_restantes,
                    url=url_alerta,
                    button_label=button_label,
                ))
            elif dias_restantes <= 2:
                # Próximo a vencer (urgente)
                alertas.append(Alert(
                    level=AlertLevel.WARNING,
                    alert_type=AlertType.MENSUAL_PROXIMO_VENCER,
                    title="Presentación Mensual Próxima a Vencer",
                    message=f"El período {nombre_mes} debe presentarse antes del {fecha_limite.strftime('%d/%m/%Y')} (¡{dias_restantes} días restantes!).",
                    cronograma=cronograma,
                    fecha_vencimiento=fecha_limite,
                    dias_restantes=dias_restantes,
                    url=url_alerta,
                    button_label=button_label,
                ))
            else:
                # Pendiente
                alertas.append(Alert(
                    level=AlertLevel.INFO,
                    alert_type=AlertType.MENSUAL_PENDIENTE,
                    title="Presentación Mensual Pendiente",
                    message=f"El período {nombre_mes} está pendiente (vence el {fecha_limite.strftime('%d/%m/%Y')}, 5° día hábil).",
                    cronograma=cronograma,
                    fecha_vencimiento=fecha_limite,
                    dias_restantes=dias_restantes,
                    url=url_alerta,
                    button_label=button_label,
                ))
        
        return alertas
