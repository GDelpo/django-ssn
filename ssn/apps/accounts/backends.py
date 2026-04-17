"""
Authentication backends for Django.

Provides multiple backends:
1. EmailBackend: Authenticate with email instead of username
2. IdentityServiceBackend: Authenticate against external identity service
"""

import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

from accounts.services import AuthenticationService

logger = logging.getLogger("accounts")
User = get_user_model()


class EmailBackend(ModelBackend):
    """
    Authenticate using email address instead of username.

    This is the standard backend for local authentication.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate with email and password.

        Args:
            request: HttpRequest object
            username: Email address (we use username field for email login)
            password: User password

        Returns:
            User object if authentication succeeds, None otherwise
        """
        try:
            user = User.objects.get(email=username)

            if user.check_password(password) and self.user_can_authenticate(user):
                logger.debug(f"✅ Email authentication successful for {username}")
                return user

            logger.warning(f"❌ Email authentication failed for {username}")
            return None

        except User.DoesNotExist:
            logger.warning(f"User not found: {username}")
            return None
        except Exception as e:
            logger.error(f"Error during email authentication: {e}")
            return None

    def get_user(self, user_id):
        """Retrieve user by ID."""
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None


class IdentityServiceBackend(ModelBackend):
    """
    Authenticate against external Identity Service.

    This backend delegates authentication to the FastAPI identity service.
    The user is synced to the local database for seamless Django integration.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate with identity service.

        Args:
            request: HttpRequest object
            username: Email address or username
            password: User password

        Returns:
            User object if authentication succeeds, None otherwise
        """
        try:
            auth_service = AuthenticationService()

            # This will use the identity service since it's configured
            user = auth_service.authenticate(username, password)

            if user and self.user_can_authenticate(user):
                logger.debug(f"✅ Identity service authentication successful for {username}")
                return user

            logger.warning(f"❌ Identity service authentication failed for {username}")
            return None

        except Exception as e:
            logger.error(f"Error during identity service authentication: {e}")
            return None

    def get_user(self, user_id):
        """Retrieve user by ID."""
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
