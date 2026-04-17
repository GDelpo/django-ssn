"""
Configuración centralizada y dinámica de logging para el proyecto Django.
Este módulo genera automáticamente la configuración de logging basada
en la lista de apps proporcionada, sin necesidad de configuración manual.
"""


def get_logging_config(debug_mode, logs_dir, apps=None):
    """
    Genera la configuración de logging basada en el modo de ejecución
    y la lista de apps proporcionada.

    Args:
        debug_mode (bool): Si la aplicación está en modo DEBUG
        logs_dir (Path): Directorio donde se guardarán los logs
        apps (list, optional): Lista de nombres de aplicaciones para configurar logging

    Returns:
        dict: Configuración de logging lista para usar en settings.py
    """
    # Ajustar el nivel de logging basado en el modo DEBUG
    log_level = "DEBUG" if debug_mode else "INFO"
    log_level_django = log_level
    log_level_console = "DEBUG" if debug_mode else "INFO"

    # Función para crear configuración de archivo de log
    def create_file_handler(name, level=None):
        if debug_mode:
            return {
                "level": level or log_level,
                "class": "logging.FileHandler",
                "filename": logs_dir / f"{name}.log",
                "formatter": "verbose",
                "encoding": "utf-8",
            }
        else:
            # En producción usamos RotatingFileHandler
            log_max_size = 10 * 1024 * 1024  # 10MB
            log_backup_count = 10
            return {
                "level": level or log_level,
                "class": "logging.handlers.RotatingFileHandler",
                "filename": logs_dir / f"{name}.log",
                "maxBytes": log_max_size,
                "backupCount": log_backup_count,
                "formatter": "verbose",
                "encoding": "utf-8",
            }

    # Configuración base
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "verbose": {
                "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
                "style": "{",
            },
            "simple": {
                "format": "{levelname} {asctime} {message}",
                "style": "{",
            },
        },
        "filters": {
            "require_debug_true": {
                "()": "django.utils.log.RequireDebugTrue",
            },
        },
        "handlers": {
            "console": {
                "level": log_level_console,
                "class": "logging.StreamHandler",
                "formatter": "simple",
            },
        },
        "loggers": {
            "django": {
                "handlers": ["console", "file_general"],
                "level": log_level_django,
                "propagate": True,
            },
            "django.request": {
                "handlers": ["file_errors"],
                "level": "ERROR",
                "propagate": False,
            },
            "root": {
                "handlers": ["console", "file_general"],
                "level": "WARNING",
            },
        },
    }

    # Crear handlers básicos del sistema
    basic_handlers = {
        "file_general": create_file_handler("general"),
        "file_errors": create_file_handler("errors", "ERROR"),
        "file_security": create_file_handler("security"),
    }

    # Agregar los handlers básicos
    logging_config["handlers"].update(basic_handlers)

    # Crear logger de seguridad
    logging_config["loggers"]["security"] = {
        "handlers": ["console", "file_security"],
        "level": "INFO",  # Siempre INFO para seguridad
        "propagate": False,
    }

    # Si no hay apps definidas, retornar la configuración básica
    if not apps:
        return logging_config

    # Crear handlers y loggers para cada app en la lista
    for app_name in apps:
        # Crear handler para la app
        handler_name = f"file_{app_name}"
        logging_config["handlers"][handler_name] = create_file_handler(app_name)

        # Crear logger para la app
        logging_config["loggers"][app_name] = {
            "handlers": ["console", handler_name, "file_errors"],
            "level": log_level,
            "propagate": False,
        }

    return logging_config
