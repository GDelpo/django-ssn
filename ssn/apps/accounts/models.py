"""
User model for the authentication system.

Supports two authentication modes:
1. Local authentication: Users stored in Django database
2. Identity Service: Authentication via FastAPI identity service
"""

import logging
from uuid import uuid4

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

logger = logging.getLogger("accounts")


class CustomUserManager(BaseUserManager):
    """Custom user manager for the User model."""

    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular user."""
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a superuser."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Custom User model with additional fields for the identity system.

    Extends Django's AbstractUser to include:
    - UUID for distributed systems
    - Email as username
    - Integration with external identity service
    - Token storage for service-to-service auth
    """

    # UUID for distributed systems (not the primary key, but useful for idempotency)
    uuid = models.UUIDField(default=uuid4, unique=True, editable=False)

    # Email is the primary login identifier
    email = models.EmailField(unique=True)

    # Disable username field in favor of email
    username = models.CharField(
        max_length=150,
        unique=False,
        blank=True,
        null=True,
        help_text="Optional field. Email is the primary identifier.",
    )

    # External identity service integration
    external_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
        help_text="ID from external identity service (if using identity service)",
    )

    # Track if user is managed by external identity service
    is_external_user = models.BooleanField(
        default=False,
        help_text="True if user is managed by identity service",
    )

    # Store JWT token from identity service (for service-to-service calls)
    identity_service_token = models.TextField(
        blank=True,
        null=True,
        help_text="JWT token from identity service for API calls",
    )

    # Track when token was obtained (for expiration)
    identity_service_token_obtained_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When the identity service token was obtained",
    )

    # User status
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive users cannot log in",
    )

    # Additional metadata
    last_login_via = models.CharField(
        max_length=50,
        blank=True,
        default="local",
        choices=[
            ("local", "Local Database"),
            ("identity_service", "Identity Service"),
            ("ldap", "LDAP"),
        ],
        help_text="Last authentication method used",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Use custom manager
    objects = CustomUserManager()

    # Use email as the login field instead of username
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["uuid"]),
            models.Index(fields=["external_id"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return self.get_full_name() or self.email

    def get_full_name(self):
        """Return the user's full name."""
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self):
        """Return the user's short name."""
        return self.first_name or self.email.split("@")[0]

    def is_token_expired(self):
        """Check if the identity service token is expired."""
        if not self.identity_service_token_obtained_at:
            return True

        from datetime import timedelta

        from django.utils import timezone

        # Assume 24 hour token expiration
        token_lifetime = timedelta(hours=24)
        return (
            timezone.now() - self.identity_service_token_obtained_at
            > token_lifetime
        )
