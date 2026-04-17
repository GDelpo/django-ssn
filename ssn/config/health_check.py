from django.db import connection
from django.http import JsonResponse


def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            db_status = "up"
    except Exception:
        db_status = "down"

    return JsonResponse(
        {
            "status": "ok",
            "database": db_status,
        }
    )
