"""
Services for authentication.

Provides flexible authentication that can use either:
1. Local Django user database
2. External Identity Service (FastAPI)
"""

import logging
from typing import Optional, Tuple

import requests
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.utils import timezone

logger = logging.getLogger("accounts")
User = get_user_model()


class IdentityServiceClient:
    """Client for communicating with the FastAPI Identity Service."""

    def __init__(self):
        self.base_url = getattr(
            settings,
            "IDENTITY_SERVICE_URL",
            "http://identity-service:8000",
        )
        self.timeout = 10
        self.verify_ssl = getattr(settings, "IDENTITY_SERVICE_VERIFY_SSL", True)

    def login(self, username: str, password: str) -> Optional[Tuple[str, dict]]:
        """
        Authenticate with identity service and get token.

        Args:
            username: Email or username
            password: User password

        Returns:
            Tuple of (token, user_data) or None if authentication fails
        """
        try:
            url = f"{self.base_url}/login"
            # OAuth2 password grant format required by FastAPI
            data = {
                "grant_type": "password",
                "username": username,
                "password": password,
                "scope": "",
                "client_id": "",
                "client_secret": "",
            }

            logger.debug(f"Authenticating with identity service: {username}")
            logger.debug(f"Identity service URL: {url}")

            response = requests.post(
                url,
                data=data,
                timeout=self.timeout,
                verify=self.verify_ssl,
            )

            if response.status_code == 200:
                token_data = response.json()
                token = token_data.get("access_token")
                logger.info(f"✅ Identity service login successful for {username}")
                return token, token_data
            else:
                logger.warning(
                    f"❌ Identity service login failed for {username}: {response.status_code}"
                )
                logger.warning(f"❌ Response body: {response.text[:500]}")
                return None

        except requests.RequestException as e:
            logger.error(f"❌ Identity service connection error: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error during identity service login: {e}")
            return None

    def verify_token(self, token: str) -> Optional[dict]:
        """
        Verify a JWT token from identity service.

        Args:
            token: JWT token

        Returns:
            Token data (decoded payload) or None if invalid
        """
        try:
            url = f"{self.base_url}/verify"
            headers = {"Authorization": f"Bearer {token}"}

            response = requests.get(
                url,
                headers=headers,
                timeout=self.timeout,
                verify=self.verify_ssl,
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Token verification failed: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error verifying token: {e}")
            return None

    def get_user_info(self, token: str) -> Optional[dict]:
        """
        Get current user info from identity service.

        Args:
            token: JWT token

        Returns:
            User data or None if request fails
        """
        try:
            url = f"{self.base_url}/me"
            headers = {"Authorization": f"Bearer {token}"}

            response = requests.get(
                url,
                headers=headers,
                timeout=self.timeout,
                verify=self.verify_ssl,
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Failed to get user info: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return None


class AuthenticationService:
    """
    Main authentication service with support for multiple backends.

    Auto-detects authentication mode:
    - If IDENTITY_SERVICE_URL is configured → Use external identity service
    - If IDENTITY_SERVICE_URL is empty → Use local database
    """

    def __init__(self):
        self.identity_service_url = getattr(settings, "IDENTITY_SERVICE_URL", "").strip()
        self.use_identity_service = bool(self.identity_service_url)
        self.identity_client = (
            IdentityServiceClient() if self.use_identity_service else None
        )
        
        auth_mode = "Identity Service" if self.use_identity_service else "Local Database"
        logger.info(f"🔐 Authentication service initialized with: {auth_mode}")

    def authenticate(self, email: str, password: str) -> Optional[User]:
        """
        Authenticate user with configured backend.

        Args:
            email: User email or username
            password: User password

        Returns:
            User object if authentication succeeds, None otherwise
        """
        if self.use_identity_service:
            return self._authenticate_with_identity_service(email, password)
        else:
            return self._authenticate_local(email, password)

    def _authenticate_local(self, email: str, password: str) -> Optional[User]:
        """Authenticate using local Django database."""
        try:
            # Try authenticating with email or username
            user = authenticate(username=email, password=password)

            if user is not None:
                # Update last_login_via
                user.last_login_via = "local"
                user.save(update_fields=["last_login_via", "last_login"])
                logger.info(f"✅ User {email} authenticated locally")
                return user

            logger.warning(f"❌ Local authentication failed for {email}")
            return None

        except Exception as e:
            logger.error(f"Error during local authentication: {e}")
            return None

    def _authenticate_with_identity_service(
        self, email: str, password: str
    ) -> Optional[User]:
        """Authenticate using external Identity Service."""
        try:
            # Get token from identity service
            result = self.identity_client.login(email, password)

            if result is None:
                logger.warning(f"❌ Identity service login failed for {email}")
                return None

            token, token_data = result

            # Get user info from identity service
            user_info = self.identity_client.get_user_info(token)

            if user_info is None:
                logger.warning(f"❌ Could not get user info from identity service")
                return None

            # Sync user in local database
            user = self._sync_user_with_identity_service(user_info, token)

            if user:
                user.last_login_via = "identity_service"
                user.save(update_fields=["last_login_via", "last_login"])
                # Set backend so django.contrib.auth.login() knows which to use
                user.backend = "accounts.backends.IdentityServiceBackend"
                logger.info(f"✅ User {email} authenticated via identity service")

            return user

        except Exception as e:
            logger.error(f"Error during identity service authentication: {e}")
            return None

    def _sync_user_with_identity_service(
        self, user_info: dict, token: str
    ) -> Optional[User]:
        """
        Sync user from identity service to local database.

        Creates or updates user in local DB based on identity service data.
        """
        try:
            external_id = user_info.get("id")
            email = user_info.get("mail") or user_info.get("email")
            first_name = user_info.get("first_name", "")
            last_name = user_info.get("last_name", "")
            role = (user_info.get("role") or "").lower()

            if not email:
                logger.error("User info from identity service missing email")
                return None

            # Map identity service role to Django permissions
            is_admin = role == "admin"

            # Get or create user
            user, created = User.objects.update_or_create(
                external_id=external_id,
                defaults={
                    "email": email,
                    "first_name": first_name,
                    "last_name": last_name,
                    "is_external_user": True,
                    "identity_service_token": token,
                    "identity_service_token_obtained_at": timezone.now(),
                    "is_active": True,
                    "is_staff": is_admin,
                    "is_superuser": is_admin,
                },
            )

            action = "created" if created else "updated"
            logger.info(f"User {action} in local DB: {email} (role={role}, is_staff={is_admin})")

            return user

        except Exception as e:
            logger.error(f"Error syncing user with identity service: {e}")
            return None

    def get_or_create_user(
        self, email: str, first_name: str = "", last_name: str = ""
    ) -> User:
        """
        Get or create a user in local database.

        Used for local authentication mode.
        """
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "first_name": first_name,
                "last_name": last_name,
                "is_external_user": False,
            },
        )
        return user
