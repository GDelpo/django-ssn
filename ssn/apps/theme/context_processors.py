from django.conf import settings


def company_info(request):
    """
    Agrega variables de configuración de la compañía al contexto de los templates.
    """
    return {
        "COMPANY_NAME": settings.COMPANY_NAME,
        "COMPANY_WEBSITE": settings.COMPANY_WEBSITE,
        "COMPANY_REGISTRATION_NUMBER": settings.SSN_API_CIA,
        "COMPANY_LOGO_URL": settings.COMPANY_LOGO_URL,
        "COMPANY_FAVICON_URL": settings.COMPANY_FAVICON_URL,
    }


def alerts_context(request):
    """
    Agrega las alertas de vencimientos al contexto de los templates.
    Solo se ejecuta para usuarios autenticados.
    """
    if not request.user.is_authenticated:
        return {"alerts": [], "alerts_count": 0}
    
    try:
        from operaciones.services.alert_service import AlertService, AlertLevel

        alertas = AlertService.get_cached_alerts()
        
        # Contar solo alertas críticas (danger y warning)
        alertas_criticas = [
            a for a in alertas 
            if a.level in [AlertLevel.DANGER, AlertLevel.WARNING]
        ]
        
        return {
            "alerts": alertas,
            "alerts_count": len(alertas_criticas),
            "has_urgent_alerts": any(a.level == AlertLevel.DANGER for a in alertas),
        }
    except Exception:
        # Si hay algún error, no mostrar alertas pero no romper la página
        return {"alerts": [], "alerts_count": 0, "has_urgent_alerts": False}
