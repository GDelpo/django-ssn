"""
Servicio para generar reportes mensuales de stocks a partir de operaciones semanales
y stocks del mes anterior.

Flujo:
1. Buscar stock del mes anterior
2. Buscar operaciones semanales del mes actual
3. Calcular stock actual = stock_anterior + constituciones - vencimientos
4. Generar registros de stock para el mes actual
"""

import calendar
import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from django.db import transaction
from django.db.models import QuerySet

# Imports solo para type hints (no se ejecutan en runtime)
if TYPE_CHECKING:
    from ..models import BaseRequestModel

logger = logging.getLogger("operaciones")


@dataclass
class GenerationResult:
    """Resultado de la generación de stocks mensuales."""

    success: bool
    message: str
    inversiones_count: int = 0
    plazos_fijos_count: int = 0
    cheques_pd_count: int = 0
    warnings: list = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []

    @property
    def total_count(self) -> int:
        return self.inversiones_count + self.plazos_fijos_count + self.cheques_pd_count


class MonthlyReportGeneratorService:
    """
    Servicio para generar automáticamente los stocks mensuales
    a partir del stock del mes anterior y las operaciones semanales.
    """

    @staticmethod
    def get_previous_month_cronograma(cronograma: str) -> str:
        """
        Dado un cronograma mensual (ej: '2025-03'), devuelve el del mes anterior.
        """
        year, month = map(int, cronograma.split("-"))
        if month == 1:
            return f"{year - 1}-12"
        return f"{year}-{month - 1:02d}"

    @staticmethod
    def get_weekly_cronogramas_for_month(cronograma: str) -> list[str]:
        """
        Dado un cronograma mensual, devuelve la lista de cronogramas semanales
        que corresponden a ese mes.

        Ejemplo: '2025-03' -> ['2025-09', '2025-10', '2025-11', '2025-12', '2025-13']
        (semanas 9 a 13 de 2025 corresponden a marzo)
        """
        year, month = map(int, cronograma.split("-"))

        # Obtener el primer y último día del mes
        first_day = date(year, month, 1)
        last_day = date(year, month, calendar.monthrange(year, month)[1])

        # Obtener las semanas ISO que cubren el mes
        first_week = first_day.isocalendar()[1]
        last_week = last_day.isocalendar()[1]

        # Manejar el caso especial de diciembre/enero
        # donde las semanas pueden "cruzar" años
        weeks = []

        if month == 12 and last_week < first_week:
            # Diciembre que termina en semana 1 del año siguiente
            for w in range(first_week, 53):
                weeks.append(f"{year}-{w:02d}")
            # Si la última semana del año es 52 y no 53
            if first_day.replace(month=12, day=31).isocalendar()[1] == 53:
                weeks.append(f"{year}-53")
            # Semana 1 del año siguiente (si aplica)
            if last_week >= 1:
                weeks.append(f"{year + 1}-01")
        elif month == 1 and first_week > 50:
            # Enero que comienza con semanas del año anterior
            weeks.append(f"{year - 1}-{first_week:02d}")
            for w in range(1, last_week + 1):
                weeks.append(f"{year}-{w:02d}")
        else:
            # Caso normal
            for w in range(first_week, last_week + 1):
                weeks.append(f"{year}-{w:02d}")

        return weeks

    @staticmethod
    def get_previous_month_stock(cronograma: str):
        """
        Obtiene la solicitud mensual del mes anterior si existe.
        """
        from ..models import BaseRequestModel, TipoEntrega
        
        prev_cronograma = MonthlyReportGeneratorService.get_previous_month_cronograma(
            cronograma
        )
        try:
            return BaseRequestModel.objects.get(
                tipo_entrega=TipoEntrega.MENSUAL, cronograma=prev_cronograma
            )
        except BaseRequestModel.DoesNotExist:
            return None

    @staticmethod
    def get_weekly_requests_for_month(cronograma: str):
        """
        Obtiene todas las solicitudes semanales que corresponden al mes indicado.
        """
        from ..models import BaseRequestModel, TipoEntrega
        
        weekly_cronogramas = (
            MonthlyReportGeneratorService.get_weekly_cronogramas_for_month(cronograma)
        )
        return BaseRequestModel.objects.filter(
            tipo_entrega=TipoEntrega.SEMANAL, cronograma__in=weekly_cronogramas
        ).order_by("cronograma")

    @staticmethod
    def get_missing_weekly_requests(cronograma: str) -> list[str]:
        """
        Devuelve la lista de cronogramas semanales que faltan para el mes indicado.
        """
        expected = set(
            MonthlyReportGeneratorService.get_weekly_cronogramas_for_month(cronograma)
        )
        existing = set(
            MonthlyReportGeneratorService.get_weekly_requests_for_month(cronograma)
            .values_list("cronograma", flat=True)
        )
        return sorted(list(expected - existing))

    @staticmethod
    def get_month_end_date(cronograma: str) -> date:
        """
        Devuelve el último día del mes para un cronograma dado.
        """
        year, month = map(int, cronograma.split("-"))
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, last_day)

    @staticmethod
    def _generate_plazo_fijo_stocks(
        target_request,
        prev_request,
        weekly_requests,
    ) -> tuple[list, list[str]]:
        """
        Genera los stocks de Plazo Fijo para el mes actual.

        Lógica:
        - Stock actual = Stock mes anterior (no vencidos) + Constituciones del mes
        - Un PF aparece en stock mientras su fecha_vencimiento > fin del mes

        El CDF en stock mensual es compuesto: {internal_number}-{original_cdf}
        """
        from ..models import PlazoFijoStock
        
        stocks = []
        warnings = []
        month_end = MonthlyReportGeneratorService.get_month_end_date(
            target_request.cronograma
        )

        # Diccionario para rastrear PFs: key = (bic, cdf_original)
        pf_registry: dict[tuple[str, str], dict] = {}

        # 1. Cargar PFs del mes anterior (si existe)
        if prev_request:
            for pf_stock in prev_request.stocks_plazofijo_mensuales.all():
                # El CDF del stock es compuesto: {internal}-{original}
                # Extraemos el CDF original
                cdf_parts = pf_stock.cdf.split("-", 1)
                cdf_original = cdf_parts[1] if len(cdf_parts) > 1 else pf_stock.cdf

                key = (pf_stock.bic, cdf_original)

                # Solo incluir si no está vencido al cierre del mes actual
                if pf_stock.fecha_vencimiento > month_end:
                    pf_registry[key] = {
                        "codigo_afectacion": pf_stock.codigo_afectacion,
                        "libre_disponibilidad": pf_stock.libre_disponibilidad,
                        "en_custodia": pf_stock.en_custodia,
                        "financiera": pf_stock.financiera,
                        "valor_contable": pf_stock.valor_contable,
                        "moneda": pf_stock.moneda,
                        "tipo_tasa": pf_stock.tipo_tasa,
                        "tasa": pf_stock.tasa,
                        "tipo_pf": pf_stock.tipo_pf,
                        "bic": pf_stock.bic,
                        "cdf": pf_stock.cdf,  # Mantener el CDF compuesto
                        "fecha_constitucion": pf_stock.fecha_constitucion,
                        "fecha_vencimiento": pf_stock.fecha_vencimiento,
                        "valor_nominal_origen": pf_stock.valor_nominal_origen,
                        "valor_nominal_nacional": pf_stock.valor_nominal_nacional,
                        "emisor_grupo_economico": pf_stock.emisor_grupo_economico,
                        "titulo_deuda": pf_stock.titulo_deuda,
                        "codigo_titulo": pf_stock.codigo_titulo,
                    }
                else:
                    logger.info(
                        f"PF {pf_stock.bic}/{pf_stock.cdf} excluido: "
                        f"vencido el {pf_stock.fecha_vencimiento}"
                    )

        # 2. Procesar operaciones semanales de Plazo Fijo (constituciones)
        internal_counter = len(pf_registry) + 1
        for weekly_req in weekly_requests:
            for pf_op in weekly_req.plazos_fijos.all():
                key = (pf_op.bic, pf_op.cdf)

                # Solo incluir si no está vencido al cierre del mes
                if pf_op.fecha_vencimiento > month_end:
                    if key not in pf_registry:
                        # Nueva constitución: crear CDF compuesto
                        cdf_compuesto = f"{internal_counter:06d}-{pf_op.cdf}"
                        pf_registry[key] = {
                            "codigo_afectacion": pf_op.codigo_afectacion,
                            "libre_disponibilidad": True,  # Default
                            "en_custodia": True,  # Default
                            "financiera": True,  # Default
                            "valor_contable": pf_op.valor_nominal_nacional,  # Por defecto
                            "moneda": pf_op.moneda,
                            "tipo_tasa": pf_op.tipo_tasa,
                            "tasa": pf_op.tasa,
                            "tipo_pf": pf_op.tipo_pf,
                            "bic": pf_op.bic,
                            "cdf": cdf_compuesto,
                            "fecha_constitucion": pf_op.fecha_constitucion,
                            "fecha_vencimiento": pf_op.fecha_vencimiento,
                            "valor_nominal_origen": pf_op.valor_nominal_origen,
                            "valor_nominal_nacional": pf_op.valor_nominal_nacional,
                            "emisor_grupo_economico": False,  # Default
                            "titulo_deuda": pf_op.titulo_deuda,
                            "codigo_titulo": pf_op.codigo_titulo,
                        }
                        internal_counter += 1
                        logger.info(
                            f"PF nuevo: {pf_op.bic}/{pf_op.cdf} -> {cdf_compuesto}"
                        )
                    else:
                        warnings.append(
                            f"PF {pf_op.bic}/{pf_op.cdf} ya existe en stock (posible renovación)."
                        )
                else:
                    logger.info(
                        f"PF operación {pf_op.bic}/{pf_op.cdf} no incluido: "
                        f"vencido el {pf_op.fecha_vencimiento}"
                    )

        # 3. Crear objetos PlazoFijoStock
        for pf_data in pf_registry.values():
            stocks.append(
                PlazoFijoStock(
                    solicitud=target_request,
                    **pf_data,
                )
            )

        return stocks, warnings

    @staticmethod
    def _generate_inversion_stocks(
        target_request,
        prev_request,
        weekly_requests,
    ) -> tuple[list, list[str]]:
        """
        Genera los stocks de Inversión para el mes actual.

        Lógica:
        - Stock actual = Stock mes anterior + Compras - Ventas (+/- Canjes)
        - Agrupado por (tipo_especie, codigo_especie, codigo_afectacion, tipo_valuacion, libre_disponibilidad)
        
        Nota: libre_disponibilidad se incluye en la key porque SSN trata como registros
        separados la misma especie con diferente disponibilidad (ej: en garantía vs libres).
        """
        from ..models import InversionStock
        
        stocks = []
        warnings = []

        # Diccionario para acumular stocks por especie
        # key = (tipo_especie, codigo_especie, codigo_afectacion, tipo_valuacion, libre_disponibilidad)
        stock_registry: dict[tuple[str, str, str, str, bool], dict] = {}

        # 1. Cargar stocks del mes anterior (si existe)
        if prev_request:
            for inv_stock in prev_request.stocks_inversion_mensuales.all():
                key = (
                    inv_stock.tipo_especie,
                    inv_stock.codigo_especie,
                    inv_stock.codigo_afectacion,
                    inv_stock.tipo_valuacion,
                    inv_stock.libre_disponibilidad,
                )
                stock_registry[key] = {
                    "codigo_afectacion": inv_stock.codigo_afectacion,
                    "libre_disponibilidad": inv_stock.libre_disponibilidad,
                    "en_custodia": inv_stock.en_custodia,
                    "financiera": inv_stock.financiera,
                    "valor_contable": inv_stock.valor_contable,
                    "tipo_especie": inv_stock.tipo_especie,
                    "codigo_especie": inv_stock.codigo_especie,
                    "cantidad_devengado_especies": inv_stock.cantidad_devengado_especies,
                    "cantidad_percibido_especies": inv_stock.cantidad_percibido_especies,
                    "tipo_valuacion": inv_stock.tipo_valuacion,
                    "con_cotizacion": inv_stock.con_cotizacion,
                    "emisor_grupo_economico": inv_stock.emisor_grupo_economico,
                    "emisor_art_ret": inv_stock.emisor_art_ret,
                    "prevision_desvalorizacion": inv_stock.prevision_desvalorizacion,
                    "fecha_pase_vt": inv_stock.fecha_pase_vt,
                    "precio_pase_vt": inv_stock.precio_pase_vt,
                    "valor_financiero": inv_stock.valor_financiero,
                }

        # 2. Procesar compras del mes
        # Las compras siempre se asignan a libre_disponibilidad=True
        for weekly_req in weekly_requests:
            for compra in weekly_req.compras.all():
                key = (
                    compra.tipo_especie,
                    compra.codigo_especie,
                    compra.codigo_afectacion,
                    compra.tipo_valuacion,
                    True,  # libre_disponibilidad
                )

                if key in stock_registry:
                    # Incrementar cantidad
                    stock_registry[key]["cantidad_devengado_especies"] += Decimal(
                        str(compra.cant_especies)
                    )
                    stock_registry[key]["cantidad_percibido_especies"] += Decimal(
                        str(compra.cant_especies)
                    )
                    logger.info(
                        f"Compra agregada: {compra.codigo_especie} +{compra.cant_especies}"
                    )
                else:
                    # Nueva posición
                    stock_registry[key] = {
                        "codigo_afectacion": compra.codigo_afectacion,
                        "libre_disponibilidad": True,  # Default
                        "en_custodia": True,  # Default
                        "financiera": True,  # Default
                        "valor_contable": Decimal("0"),  # Se debe calcular manualmente
                        "tipo_especie": compra.tipo_especie,
                        "codigo_especie": compra.codigo_especie,
                        "cantidad_devengado_especies": Decimal(str(compra.cant_especies)),
                        "cantidad_percibido_especies": Decimal(str(compra.cant_especies)),
                        "tipo_valuacion": compra.tipo_valuacion,
                        "con_cotizacion": True,  # Default
                        "emisor_grupo_economico": False,  # Default
                        "emisor_art_ret": False,  # Default
                        "prevision_desvalorizacion": None,
                        "fecha_pase_vt": None,
                        "precio_pase_vt": None,
                        "valor_financiero": None,
                    }
                    logger.info(
                        f"Nueva posición: {compra.codigo_especie} x {compra.cant_especies}"
                    )

        # 3. Procesar ventas del mes
        # Las ventas se restan del stock con libre_disponibilidad=True
        for weekly_req in weekly_requests:
            for venta in weekly_req.ventas.all():
                key = (
                    venta.tipo_especie,
                    venta.codigo_especie,
                    venta.codigo_afectacion,
                    venta.tipo_valuacion,
                    True,  # libre_disponibilidad
                )

                if key in stock_registry:
                    # Decrementar cantidad
                    stock_registry[key]["cantidad_devengado_especies"] -= Decimal(
                        str(venta.cant_especies)
                    )
                    stock_registry[key]["cantidad_percibido_especies"] -= Decimal(
                        str(venta.cant_especies)
                    )
                    logger.info(
                        f"Venta procesada: {venta.codigo_especie} -{venta.cant_especies}"
                    )

                    # Verificar si la cantidad queda en cero o negativa
                    if stock_registry[key]["cantidad_percibido_especies"] <= 0:
                        logger.info(
                            f"Posición cerrada: {venta.codigo_especie}"
                        )
                else:
                    warnings.append(
                        f"Venta sin posición previa: {venta.codigo_especie}. "
                        "Verifique los datos del mes anterior."
                    )

        # 4. Procesar canjes del mes
        for weekly_req in weekly_requests:
            for canje in weekly_req.canjes.all():
                # Los canjes tienen especie_origen y especie_destino
                # Aquí depende de la estructura del modelo de canje
                # Por ahora, solo registramos una advertencia
                warnings.append(
                    f"Canje detectado en semana {weekly_req.cronograma}. "
                    "Los canjes requieren procesamiento manual."
                )

        # 5. Crear objetos InversionStock (solo posiciones con cantidad > 0)
        for key, inv_data in stock_registry.items():
            if inv_data["cantidad_percibido_especies"] > 0:
                stocks.append(
                    InversionStock(
                        solicitud=target_request,
                        **inv_data,
                    )
                )

        return stocks, warnings

    @staticmethod
    def _generate_cheque_pd_stocks(
        target_request,
        prev_request,
        weekly_requests,
    ) -> tuple[list, list[str]]:
        """
        Genera los stocks de Cheques Pago Diferido para el mes actual.

        Nota: Las operaciones semanales no incluyen cheques PD directamente,
        por lo que solo copiamos del mes anterior (si no están vencidos).
        """
        from ..models import ChequePagoDiferidoStock
        
        stocks = []
        warnings = []
        month_end = MonthlyReportGeneratorService.get_month_end_date(
            target_request.cronograma
        )

        if prev_request:
            for cpd_stock in prev_request.stocks_chequespd_mensuales.all():
                # Solo incluir si no está vencido al cierre del mes
                if cpd_stock.fecha_vencimiento > month_end:
                    stocks.append(
                        ChequePagoDiferidoStock(
                            solicitud=target_request,
                            codigo_afectacion=cpd_stock.codigo_afectacion,
                            libre_disponibilidad=cpd_stock.libre_disponibilidad,
                            en_custodia=cpd_stock.en_custodia,
                            financiera=cpd_stock.financiera,
                            valor_contable=cpd_stock.valor_contable,
                            moneda=cpd_stock.moneda,
                            tipo_tasa=cpd_stock.tipo_tasa,
                            tasa=cpd_stock.tasa,
                            codigo_sgr=cpd_stock.codigo_sgr,
                            codigo_cheque=cpd_stock.codigo_cheque,
                            fecha_emision=cpd_stock.fecha_emision,
                            fecha_vencimiento=cpd_stock.fecha_vencimiento,
                            valor_nominal=cpd_stock.valor_nominal,
                            valor_adquisicion=cpd_stock.valor_adquisicion,
                            grupo_economico=cpd_stock.grupo_economico,
                            fecha_adquisicion=cpd_stock.fecha_adquisicion,
                        )
                    )

        if not stocks and not prev_request:
            warnings.append(
                "No hay stock de Cheques Pago Diferido del mes anterior. "
                "Si la compañía opera con CPD, ingrese los stocks manualmente."
            )

        return stocks, warnings

    @staticmethod
    @transaction.atomic
    def generate_monthly_stocks(target_request) -> GenerationResult:
        """
        Genera todos los stocks mensuales para una solicitud dada.

        Args:
            target_request: Solicitud mensual donde se generarán los stocks.

        Returns:
            GenerationResult con el resultado de la operación.
        """
        from ..models import (
            InversionStock,
            PlazoFijoStock,
            ChequePagoDiferidoStock,
            TipoEntrega,
        )
        
        if target_request.tipo_entrega != TipoEntrega.MENSUAL:
            return GenerationResult(
                success=False,
                message="La solicitud no es de tipo mensual.",
            )

        cronograma = target_request.cronograma
        all_warnings = []

        # Verificar si ya tiene stocks
        existing_count = (
            target_request.stocks_inversion_mensuales.count()
            + target_request.stocks_plazofijo_mensuales.count()
            + target_request.stocks_chequespd_mensuales.count()
        )
        if existing_count > 0:
            return GenerationResult(
                success=False,
                message=f"La solicitud ya tiene {existing_count} stocks. "
                "Elimínelos primero si desea regenerar.",
            )

        # Obtener solicitudes relacionadas
        prev_request = MonthlyReportGeneratorService.get_previous_month_stock(cronograma)
        weekly_requests = MonthlyReportGeneratorService.get_weekly_requests_for_month(
            cronograma
        )

        # Verificar semanas faltantes
        missing_weeks = MonthlyReportGeneratorService.get_missing_weekly_requests(
            cronograma
        )
        if missing_weeks:
            all_warnings.append(
                f"Faltan las semanas: {', '.join(missing_weeks)}. "
                "Los stocks generados pueden estar incompletos."
            )

        # Verificar si hay datos previos
        if not prev_request and weekly_requests.count() == 0:
            return GenerationResult(
                success=False,
                message="No hay stock del mes anterior ni operaciones semanales. "
                "No es posible generar el reporte mensual.",
            )

        if not prev_request:
            all_warnings.append(
                "No existe stock del mes anterior. "
                "Los stocks se generarán solo con las operaciones del mes."
            )

        # Generar stocks
        pf_stocks, pf_warnings = (
            MonthlyReportGeneratorService._generate_plazo_fijo_stocks(
                target_request, prev_request, weekly_requests
            )
        )
        all_warnings.extend(pf_warnings)

        inv_stocks, inv_warnings = (
            MonthlyReportGeneratorService._generate_inversion_stocks(
                target_request, prev_request, weekly_requests
            )
        )
        all_warnings.extend(inv_warnings)

        cpd_stocks, cpd_warnings = (
            MonthlyReportGeneratorService._generate_cheque_pd_stocks(
                target_request, prev_request, weekly_requests
            )
        )
        all_warnings.extend(cpd_warnings)

        # Guardar stocks
        if pf_stocks:
            PlazoFijoStock.objects.bulk_create(pf_stocks)
        if inv_stocks:
            InversionStock.objects.bulk_create(inv_stocks)
        if cpd_stocks:
            ChequePagoDiferidoStock.objects.bulk_create(cpd_stocks)

        total = len(pf_stocks) + len(inv_stocks) + len(cpd_stocks)
        logger.info(
            f"Generados {total} stocks mensuales para {cronograma}: "
            f"{len(inv_stocks)} inversiones, {len(pf_stocks)} PF, {len(cpd_stocks)} CPD"
        )

        return GenerationResult(
            success=True,
            message=f"Se generaron {total} stocks mensuales correctamente.",
            inversiones_count=len(inv_stocks),
            plazos_fijos_count=len(pf_stocks),
            cheques_pd_count=len(cpd_stocks),
            warnings=all_warnings,
        )

    @staticmethod
    def delete_generated_stocks(target_request) -> int:
        """
        Elimina todos los stocks generados para una solicitud mensual.

        Returns:
            Número total de stocks eliminados.
        """
        count = 0
        count += target_request.stocks_inversion_mensuales.all().delete()[0]
        count += target_request.stocks_plazofijo_mensuales.all().delete()[0]
        count += target_request.stocks_chequespd_mensuales.all().delete()[0]

        logger.info(f"Eliminados {count} stocks de la solicitud {target_request.uuid}")
        return count
