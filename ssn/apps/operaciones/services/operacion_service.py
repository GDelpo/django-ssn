import logging

from ..models import TipoEntrega

logger = logging.getLogger("operaciones")


class OperacionesService:
    """
    Service central para lógica de consulta y agrupación de operaciones.
    """

    @staticmethod
    def get_all_operaciones(base_request):
        """
        Devuelve TODAS las operaciones asociadas a una solicitud, como una lista única ordenada.
        """
        if base_request.tipo_entrega == TipoEntrega.SEMANAL:
            compras = base_request.compras.all()
            ventas = base_request.ventas.all()
            canjes = base_request.canjes.all()
            plazos_fijos = base_request.plazos_fijos.all()
            operaciones = (
                list(compras) + list(ventas) + list(canjes) + list(plazos_fijos)
            )
            # Ordenar por fecha de movimiento
            operaciones.sort(key=lambda op: op.fecha_operacion)
        elif base_request.tipo_entrega == TipoEntrega.MENSUAL:
            inversiones = base_request.stocks_inversion_mensuales.all()
            plazos_fijos = base_request.stocks_plazofijo_mensuales.all()
            cheques_pd = base_request.stocks_chequespd_mensuales.all()
            operaciones = list(inversiones) + list(plazos_fijos) + list(cheques_pd)
        return operaciones

    @staticmethod
    def get_count_by_tipo(base_request):
        """
        Devuelve un dict con el conteo de operaciones por tipo.
        """
        return {
            "compras": base_request.compras.count(),
            "ventas": base_request.ventas.count(),
            "canjes": base_request.canjes.count(),
            "plazos_fijos": base_request.plazos_fijos.count(),
        }

    @staticmethod
    def get_total_operaciones(base_request):
        """
        Devuelve el total sumando los valores del dict de counts.
        """
        counts = OperacionesService.get_count_by_tipo(base_request)
        return sum(counts.values())

    @staticmethod
    def get_extra_info(base_request):
        """
        Devuelve información extra para mostrar en los templates.
        """
        return [
            ("Tipo de Entrega", base_request.tipo_entrega or "—"),
            ("Cronograma", base_request.cronograma or "—"),
            ("Operaciones", OperacionesService.get_total_operaciones(base_request)),
        ]

    @staticmethod
    def has_changes_since_rectification(base_request):
        """
        Versión eficiente que delega el trabajo a la base de datos.
        Recomendada para producción.
        """
        last_submission_time = base_request.send_at
        if not last_submission_time:
            return False

        related_managers_names = []
        if base_request.tipo_entrega == "Semanal":
            related_managers_names = ["compras", "ventas", "canjes", "plazos_fijos"]
        elif base_request.tipo_entrega == "Mensual":
            related_managers_names = [
                "stocks_inversion_mensuales",
                "stocks_plazofijo_mensuales",
                "stocks_chequespd_mensuales",
            ]

        # Pregunta a la base de datos si "existe" algún registro que coincida
        for manager_name in related_managers_names:
            manager = getattr(base_request, manager_name)
            if manager.filter(updated_at__gt=last_submission_time).exists():
                return True  # La BD encontró uno. Fin.

        return False

    @staticmethod
    def revert_new_operations(base_request):
        """
        Busca y elimina todas las operaciones creadas durante una sesión de
        rectificación para revertir los cambios.
        """
        last_submission_time = base_request.send_at
        if not last_submission_time:
            return 0  # No hay nada que revertir

        # Define qué relaciones chequear
        related_managers_names = []
        if base_request.tipo_entrega == TipoEntrega.SEMANAL:
            related_managers_names = ["compras", "ventas", "canjes", "plazos_fijos"]
        elif base_request.tipo_entrega == TipoEntrega.MENSUAL:
            related_managers_names = [
                "stocks_inversion_mensuales",
                "stocks_plazofijo_mensuales",
                "stocks_chequespd_mensuales",
            ]

        total_deleted_count = 0
        # Itera y elimina las operaciones nuevas
        for manager_name in related_managers_names:
            manager = getattr(base_request, manager_name)
            ops_to_delete = manager.filter(created_at__gt=last_submission_time)

            if ops_to_delete.exists():
                count, _ = ops_to_delete.delete()
                total_deleted_count += count
                logger.info(
                    f"Reversión: Se eliminaron {count} operaciones de '{manager_name}' "
                    f"para la solicitud {base_request.uuid}."
                )

        return total_deleted_count
