"""
Modelos para stocks mensuales: Inversión, Plazo Fijo, Cheque Pago Diferido.
"""

from .inversion import InversionStock
from .plazo_fijo import PlazoFijoStock
from .cheque_pd import ChequePagoDiferidoStock

__all__ = [
    "InversionStock",
    "PlazoFijoStock",
    "ChequePagoDiferidoStock",
]
