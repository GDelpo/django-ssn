def get_mapping_model():
    """
    Obtiene un diccionario de mapeo entre códigos de operación y sus modelos correspondientes.

    Returns:
        dict: Diccionario con códigos como claves y clases de modelo como valores.
            Semanales:
                'C': CompraOperacion
                'V': VentaOperacion
                'J': CanjeOperacion
                'P': PlazoFijoOperacion
            Mensuales (Stocks):
                'SI': InversionStock
                'SP': PlazoFijoStock
                'SC': ChequePagoDiferidoStock
    """
    from ..models import (
        CanjeOperacion,
        CompraOperacion,
        PlazoFijoOperacion,
        VentaOperacion,
        InversionStock,
        PlazoFijoStock,
        ChequePagoDiferidoStock,
    )

    return {
        # Operaciones semanales
        "C": CompraOperacion,
        "V": VentaOperacion,
        "J": CanjeOperacion,
        "P": PlazoFijoOperacion,
        # Stocks mensuales
        "SI": InversionStock,
        "SP": PlazoFijoStock,
        "SC": ChequePagoDiferidoStock,
    }


def get_related_names_map():
    """
    Obtiene un diccionario de mapeo entre códigos de operación y sus nombres de relación inversa.

    Returns:
        dict: Diccionario con códigos como claves y nombres de relación inversa como valores.
            'C': 'compras'
            'V': 'ventas'
            'J': 'canjes'
            'P': 'plazos_fijos'
    """
    return {"C": "compras", "V": "ventas", "J": "canjes", "P": "plazos_fijos"}
