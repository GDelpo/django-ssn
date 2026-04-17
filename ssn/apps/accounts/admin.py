"""
Django admin configuration for accounts app.

Registers User model and other models.
"""

import logging

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from accounts.models import User

logger = logging.getLogger("accounts")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom admin for User model."""

    list_display = (
        "email",
        "first_name",
        "last_name",
        "is_active",
        "is_staff",
        "last_login_via",
        "created_at",
    )
    list_filter = (
        "is_active",
        "is_staff",
        "is_superuser",
        "is_external_user",
        "last_login_via",
        "created_at",
    )
    search_fields = ("email", "first_name", "last_name", "uuid", "external_id")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            _("Personal info"),
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "username",
                )
            },
        ),
        (
            _("External Identity"),
            {
                "fields": (
                    "is_external_user",
                    "external_id",
                    "identity_service_token",
                    "identity_service_token_obtained_at",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (
            _("Important dates"),
            {
                "fields": (
                    "last_login",
                    "last_login_via",
                    "created_at",
                    "updated_at",
                )
            },
        ),
        (
            _("System"),
            {
                "fields": ("uuid",),
                "classes": ("collapse",),
            },
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2"),
            },
        ),
    )

    readonly_fields = (
        "uuid",
        "created_at",
        "updated_at",
        "last_login",
        "identity_service_token_obtained_at",
    )

    ordering = ("-created_at",)
