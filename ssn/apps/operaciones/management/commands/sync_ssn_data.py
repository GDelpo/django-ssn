"""
Management command para sincronizar datos históricos desde la API de SSN.

Uso:
    python manage.py sync_ssn_data --period semanal --year 2025
    python manage.py sync_ssn_data --period mensual --year 2025
    python manage.py sync_ssn_data --period semanal --year 2025 --dry-run
"""

import datetime
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from operaciones.helpers.date_utils import (
    calcular_quinto_dia_habil,
    generate_monthly_options,
    generate_week_options,
    get_last_week_id,
)
from operaciones.models import (
    BaseRequestModel,
    CanjeOperacion,
    ChequePagoDiferidoStock,
    CompraOperacion,
    DetalleOperacionCanje,
    EstadoSolicitud,
    InversionStock,
    PlazoFijoOperacion,
    PlazoFijoStock,
    TipoEntrega,
    VentaOperacion,
)

logger = logging.getLogger(__name__)


# Mapeo de tipo de operación a modelo (para semanales)
OPERATION_MODEL_MAP = {
    "C": CompraOperacion,
    "V": VentaOperacion,
    "J": CanjeOperacion,
    "P": PlazoFijoOperacion,
}

# Mapeo de tipo de stock a modelo (para mensuales)
STOCK_MODEL_MAP = {
    "I": InversionStock,
    "P": PlazoFijoStock,
    "C": ChequePagoDiferidoStock,
}


class Command(BaseCommand):
    help = "Sincroniza datos históricos desde la API de SSN a la base de datos local"

    def add_arguments(self, parser):
        parser.add_argument(
            "--period",
            type=str,
            choices=["semanal", "mensual"],
            required=True,
            help="Tipo de período a sincronizar (semanal o mensual)",
        )
        parser.add_argument(
            "--year",
            type=int,
            default=datetime.date.today().year,
            help="Año a sincronizar (default: año actual)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simular sin guardar en la base de datos",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Sobrescribir registros existentes",
        )
        parser.add_argument(
            "--cronograma",
            type=str,
            help="Sincronizar solo un cronograma específico (ej: 2025-15)",
        )

    def handle(self, *args, **options):
        period = options["period"]
        year = options["year"]
        dry_run = options["dry_run"]
        force = options["force"]
        specific_cronograma = options.get("cronograma")

        self.stdout.write(
            self.style.NOTICE(f"Sincronizando datos {period} para el año {year}...")
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("🔍 Modo DRY-RUN activado"))

        # Obtener el cliente SSN
        try:
            ssn_client = apps.get_app_config("ssn_client").ssn_client
        except Exception as e:
            raise CommandError(f"Error al obtener cliente SSN: {e}")

        # Generar lista de cronogramas a sincronizar
        if specific_cronograma:
            cronogramas = [(specific_cronograma, None)]
        else:
            cronogramas = self._get_available_cronogramas(period, year)

        self.stdout.write(f"📅 Cronogramas a procesar: {len(cronogramas)}")

        # Estadísticas
        stats = {
            "processed": 0,
            "created": 0,
            "skipped": 0,
            "errors": 0,
            "operations_created": 0,
        }

        for cronograma_id, presentation_date in cronogramas:
            try:
                result = self._sync_cronograma(
                    ssn_client=ssn_client,
                    period=period,
                    cronograma_id=cronograma_id,
                    presentation_date=presentation_date,
                    dry_run=dry_run,
                    force=force,
                )
                stats["processed"] += 1
                if result["created"]:
                    stats["created"] += 1
                    stats["operations_created"] += result["operations"]
                elif result["skipped"]:
                    stats["skipped"] += 1
            except Exception as e:
                stats["errors"] += 1
                self.stdout.write(
                    self.style.ERROR(f"  ❌ Error en {cronograma_id}: {e}")
                )
                logger.exception(f"Error sincronizando {cronograma_id}")

        # Actualizar created_at = send_at para todos los registros sincronizados
        # (auto_now_add=True ignora valores en create(), usamos UPDATE masivo)
        updated = BaseRequestModel.objects.filter(
            send_at__isnull=False
        ).update(created_at=F('send_at'))
        
        if updated:
            self.stdout.write(f"\n🔄 Actualizado created_at en {updated} registros")

        # Resumen final
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.SUCCESS("📊 RESUMEN:"))
        self.stdout.write(f"  Procesados: {stats['processed']}")
        self.stdout.write(f"  Creados: {stats['created']}")
        self.stdout.write(f"  Saltados (ya existían): {stats['skipped']}")
        self.stdout.write(f"  Errores: {stats['errors']}")
        self.stdout.write(f"  Operaciones/Stocks creados: {stats['operations_created']}")

    def _get_available_cronogramas(
        self, period: str, year: int
    ) -> List[Tuple[str, Optional[str]]]:
        """
        Obtiene la lista de cronogramas disponibles hasta la fecha actual.
        Para años pasados, incluye todas las semanas/meses.
        Para el año actual, incluye solo hasta la semana/mes actual.
        
        Returns:
            Lista de tuplas (cronograma_id, fecha_presentacion)
        """
        today = datetime.date.today()
        is_past_year = year < today.year

        if period == "semanal":
            weeks = generate_week_options(year)
            
            # Para años pasados, incluir todas las semanas
            if is_past_year:
                last_week_id = weeks[-1][0] if weeks else None
            else:
                # Para el año actual, usar la última semana vencida
                last_week_id = get_last_week_id(weeks)
            
            available = []
            for week_id, date_range in weeks:
                # Calcular fecha de presentación (lunes siguiente)
                end_str = date_range.split(" - ")[1].strip()
                end_date = datetime.datetime.strptime(end_str, "%d/%m/%Y").date()
                presentation_date = (end_date + datetime.timedelta(days=1)).isoformat()
                
                available.append((week_id, presentation_date))
                if week_id == last_week_id:
                    break
            return available

        elif period == "mensual":
            options = generate_monthly_options(year)
            available = []
            
            for month_id, _ in options:
                # Extraer año y mes del ID
                y, m = map(int, month_id.split("-"))
                
                # Para años pasados, incluir todos los meses
                # Para el año actual, solo meses ya cerrados (mes actual - 1)
                if is_past_year or (y == today.year and m < today.month):
                    # Fecha de presentación: 5to día hábil del mes siguiente
                    if m == 12:
                        presentation_date = calcular_quinto_dia_habil(y + 1, 1)
                    else:
                        presentation_date = calcular_quinto_dia_habil(y, m + 1)
                    available.append((month_id, presentation_date.isoformat()))
            
            return available

        return []

    def _sync_cronograma(
        self,
        ssn_client,
        period: str,
        cronograma_id: str,
        presentation_date: Optional[str],
        dry_run: bool,
        force: bool,
    ) -> Dict[str, Any]:
        """
        Sincroniza un cronograma específico desde SSN.
        """
        tipo_entrega = TipoEntrega.SEMANAL if period == "semanal" else TipoEntrega.MENSUAL
        
        # Verificar si ya existe
        existing = BaseRequestModel.objects.filter(
            cronograma=cronograma_id,
            tipo_entrega=tipo_entrega,
        ).first()

        if existing and not force:
            self.stdout.write(f"  ⏭️  {cronograma_id} ya existe (saltando)")
            return {"created": False, "skipped": True, "operations": 0}

        # Consultar la API de SSN
        resource = f"entrega{period.capitalize()}?codigoCompania={settings.SSN_API_CIA}&cronograma={cronograma_id}"
        data, status = ssn_client.get_resource(resource)

        if status != 200:
            raise Exception(f"API respondió con status {status}: {data}")

        # Normalizar datos
        normalized = self._normalize_data(data)

        if dry_run:
            ops_count = len(normalized.get("operaciones", [])) or len(
                normalized.get("stocks", [])
            )
            self.stdout.write(
                f"  🔍 {cronograma_id}: {ops_count} operaciones/stocks (dry-run)"
            )
            return {"created": True, "skipped": False, "operations": ops_count}

        # Crear en la base de datos
        with transaction.atomic():
            # Eliminar existente si force=True
            if existing and force:
                self.stdout.write(f"  🗑️  Eliminando {cronograma_id} existente...")
                existing.delete()

            # Crear BaseRequestModel
            # Usamos la fecha de presentación para send_at
            presentation_datetime = timezone.make_aware(
                datetime.datetime.fromisoformat(presentation_date)
            ) if presentation_date else timezone.now()
            
            base_request = BaseRequestModel.objects.create(
                codigo_compania=normalized.get("codigo_compania", settings.SSN_API_CIA),
                tipo_entrega=tipo_entrega,
                cronograma=cronograma_id,
                estado=EstadoSolicitud.PRESENTADO,
                send_at=presentation_datetime,
            )

            # Crear operaciones/stocks
            if period == "semanal":
                ops_count = self._create_operations(
                    base_request, normalized.get("operaciones", [])
                )
            else:
                ops_count = self._create_stocks(
                    base_request, normalized.get("stocks", [])
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"  ✅ {cronograma_id}: {ops_count} operaciones/stocks creados"
            )
        )
        return {"created": True, "skipped": False, "operations": ops_count}

    def _create_operations(
        self, base_request: BaseRequestModel, operations: List[Dict]
    ) -> int:
        """Crea las operaciones semanales asociadas a una solicitud."""
        count = 0
        for op_data in operations:
            tipo = op_data.pop("tipo_operacion", None)
            model_class = OPERATION_MODEL_MAP.get(tipo)

            if not model_class:
                logger.warning(f"Tipo de operación desconocido: {tipo}")
                continue

            # Remover campos que no corresponden al modelo
            op_data.pop("tipo_entrega", None)
            op_data.pop("codigo_compania", None)
            op_data.pop("cronograma", None)

            # Manejar canjes con detalles
            if tipo == "J":
                detalles = op_data.pop("detalles", [])
                canje = model_class.objects.create(solicitud=base_request, **op_data)
                for detalle in detalles:
                    DetalleOperacionCanje.objects.create(canje=canje, **detalle)
            else:
                model_class.objects.create(solicitud=base_request, **op_data)

            count += 1

        return count

    def _create_stocks(
        self, base_request: BaseRequestModel, stocks: List[Dict]
    ) -> int:
        """Crea los stocks mensuales asociados a una solicitud."""
        count = 0
        for stock_data in stocks:
            tipo = stock_data.pop("tipo", None)
            model_class = STOCK_MODEL_MAP.get(tipo)

            if not model_class:
                logger.warning(f"Tipo de stock desconocido: {tipo}")
                continue

            # Remover campos que no corresponden al modelo
            stock_data.pop("tipo_entrega", None)
            stock_data.pop("codigo_compania", None)
            stock_data.pop("cronograma", None)

            # Convertir None a 0 en campos decimales requeridos
            stock_data = self._fix_null_decimals(stock_data)

            model_class.objects.create(solicitud=base_request, **stock_data)
            count += 1

        return count

    def _fix_null_decimals(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convierte valores None a 0 en campos decimales requeridos.
        La API de SSN a veces devuelve null en campos que deberían ser numéricos.
        """
        # Campos decimales que no permiten null en los modelos
        required_decimal_fields = {
            "valor_contable",
            "cantidad_devengado_especies",
            "cantidad_percibido_especies",
            "tasa",
            "valor_nominal",
            "monto",
        }

        for field in required_decimal_fields:
            if field in data and data[field] is None:
                data[field] = 0

        return data

    def _normalize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normaliza los datos de la API de SSN:
        - Convierte camelCase a snake_case
        - Convierte fechas ddmmyyyy a ISO (yyyy-mm-dd)
        - Elimina strings vacíos
        """
        data = self._dict_keys_to_snake(data)
        data = self._convert_dates(data)
        data = self._remove_empty_strings(data)
        return data

    def _camel_to_snake(self, name: str) -> str:
        """Convierte camelCase/PascalCase a snake_case."""
        s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
        return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()

    def _dict_keys_to_snake(self, obj: Any) -> Any:
        """Recursivamente convierte keys de dict a snake_case."""
        if isinstance(obj, dict):
            return {
                self._camel_to_snake(k): self._dict_keys_to_snake(v)
                for k, v in obj.items()
            }
        elif isinstance(obj, list):
            return [self._dict_keys_to_snake(item) for item in obj]
        return obj

    def _convert_dates(self, obj: Any) -> Any:
        """Recursivamente convierte fechas ddmmyyyy a ISO."""
        if isinstance(obj, dict):
            new_dict = {}
            for k, v in obj.items():
                if "fecha" in k.lower() and isinstance(v, str) and re.fullmatch(
                    r"\d{8}", v
                ):
                    try:
                        new_dict[k] = datetime.datetime.strptime(
                            v, "%d%m%Y"
                        ).date().isoformat()
                    except ValueError:
                        new_dict[k] = v
                else:
                    new_dict[k] = self._convert_dates(v)
            return new_dict
        elif isinstance(obj, list):
            return [self._convert_dates(item) for item in obj]
        return obj

    def _remove_empty_strings(self, obj: Any) -> Any:
        """
        Recursivamente elimina pares key:value donde value es string vacío.
        También convierte el string "null" a None real de Python.
        """
        if isinstance(obj, dict):
            result = {}
            for k, v in obj.items():
                if v == "":
                    continue  # Eliminar strings vacíos
                elif v == "null":
                    result[k] = None  # Convertir string "null" a None
                else:
                    result[k] = self._remove_empty_strings(v)
            return result
        elif isinstance(obj, list):
            return [self._remove_empty_strings(item) for item in obj]
        return obj
