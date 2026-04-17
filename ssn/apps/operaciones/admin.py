from django.contrib import admin

from .models import (
    BaseRequestModel,
    CanjeOperacion,
    CompraOperacion,
    PlazoFijoOperacion,
    VentaOperacion,
)

admin.site.register(
    [
        BaseRequestModel,
        CompraOperacion,
        VentaOperacion,
        CanjeOperacion,
        PlazoFijoOperacion,
    ]
)
