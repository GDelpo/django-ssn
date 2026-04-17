from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
    verbose_name = "Authentication"

    def ready(self):
        """Import signals when the app is ready."""
        import accounts.signals  # noqa: F401
