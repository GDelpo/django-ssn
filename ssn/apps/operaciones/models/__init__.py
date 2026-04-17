"""
Módulo principal de modelos que expone los modelos base y de operación.

Estructura:
- base/: Clases base abstractas y mixins
- semanal/: Operaciones semanales (Compra, Venta, Canje, Plazo Fijo)
- mensual/: Stocks mensuales (Inversión, Plazo Fijo, Cheque PD)
"""

# Choices
from .choices import (
    EstadoSolicitud,
    TipoEntrega,
    TipoEspecie,
    TipoOperacion,
    TipoTasa,
    TipoValuacion,
    TipoStock,
)

# Modelo de solicitud base
from .base import BaseRequestModel

# Operaciones semanales
from .semanal import (
    CompraOperacion,
    VentaOperacion,
    CanjeOperacion,
    PlazoFijoOperacion,
    DetalleOperacionCanje,
)

# Stocks mensuales
from .mensual import (
    InversionStock,
    PlazoFijoStock,
    ChequePagoDiferidoStock,
)


__all__ = [
    # Choices
    "EstadoSolicitud",
    "TipoEntrega",
    "TipoEspecie",
    "TipoOperacion",
    "TipoTasa",
    "TipoValuacion",
    "TipoStock",
    # Base
    "BaseRequestModel",
    # Semanales
    "CompraOperacion",
    "VentaOperacion",
    "CanjeOperacion",
    "PlazoFijoOperacion",
    "DetalleOperacionCanje",
    # Mensuales
    "InversionStock",
    "PlazoFijoStock",
    "ChequePagoDiferidoStock",
]

