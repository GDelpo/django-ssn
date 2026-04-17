import json

from django.contrib import admin
from django.utils.html import format_html

from .models import SolicitudResponse


@admin.register(SolicitudResponse)
class SolicitudResponseAdmin(admin.ModelAdmin):
    list_display = ("id", "solicitud", "endpoint", "status_badge", "es_error", "created_at")
    list_filter = ("es_error", "endpoint", "status_http")
    search_fields = ("solicitud__uuid", "endpoint")
    ordering = ("-created_at",)
    readonly_fields = (
        "solicitud",
        "endpoint",
        "status_http",
        "es_error",
        "payload_pretty",
        "respuesta_pretty",
        "created_at",
        "updated_at",
    )
    fields = readonly_fields

    def status_badge(self, obj):
        color = "#e74c3c" if obj.es_error else "#27ae60"
        return format_html(
            "<span style='color:white;background:{};padding:2px 6px;"
            "border-radius:3px;font-size:11px'>{}</span>",
            color,
            obj.status_http,
        )
    status_badge.short_description = "HTTP"

    def payload_pretty(self, obj):
        return format_html(
            "<pre style='white-space:pre-wrap;font-size:11px'>{}</pre>",
            json.dumps(obj.payload_enviado, indent=2, ensure_ascii=False),
        )
    payload_pretty.short_description = "Payload enviado"

    def respuesta_pretty(self, obj):
        color = "#c0392b" if obj.es_error else "#1a5276"
        return format_html(
            "<pre style='white-space:pre-wrap;font-size:11px;color:{}'>{}</pre>",
            color,
            json.dumps(obj.respuesta, indent=2, ensure_ascii=False),
        )
    respuesta_pretty.short_description = "Respuesta SSN"
