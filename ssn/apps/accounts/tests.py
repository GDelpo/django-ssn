"""
Tests for accounts app.

Test authentication, user creation, and views.
"""

from unittest.mock import patch

from django.contrib.auth import authenticate, get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase, Client, override_settings
from django.urls import reverse

from accounts.services import AuthenticationService

User = get_user_model()


class UserModelTests(TestCase):
    """Tests for User model."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User",
        )

    def test_user_creation(self):
        """Test that user is created correctly."""
        self.assertEqual(self.user.email, "test@example.com")
        self.assertEqual(self.user.first_name, "Test")
        self.assertEqual(self.user.last_name, "User")
        self.assertTrue(self.user.is_active)
        self.assertFalse(self.user.is_external_user)

    def test_user_str(self):
        """Test user string representation."""
        self.assertEqual(str(self.user), "Test User")

    def test_get_full_name(self):
        """Test get_full_name method."""
        self.assertEqual(self.user.get_full_name(), "Test User")

    def test_get_short_name(self):
        """Test get_short_name method."""
        self.assertEqual(self.user.get_short_name(), "Test")


class LoginViewTests(TestCase):
    """Tests for login view."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.login_url = reverse("accounts:login")
        self.home_url = reverse("theme:index")
        
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
        )

    def test_login_page_loads(self):
        """Test that login page loads."""
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/login.html")

    def test_login_with_valid_credentials(self):
        """Test login with valid credentials."""
        response = self.client.post(
            self.login_url,
            {
                "email": "test@example.com",
                "password": "testpass123",
                "remember_me": False,
            },
        )
        # Should redirect to home
        self.assertEqual(response.status_code, 302)

    def test_login_with_invalid_credentials(self):
        """Test login with invalid credentials."""
        response = self.client.post(
            self.login_url,
            {
                "email": "test@example.com",
                "password": "wrongpassword",
                "remember_me": False,
            },
        )
        # Should stay on login page
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Incorrect email or password. Please try again.",
            [str(message) for message in get_messages(response.wsgi_request)],
        )

    def test_invalid_password_does_not_recurse_through_backends(self):
        """A wrong password reaches the local lookup once, not once per recursion."""
        with patch.object(
            AuthenticationService,
            "_authenticate_local",
            autospec=True,
            side_effect=AuthenticationService._authenticate_local,
        ) as local:
            self.assertIsNone(
                AuthenticationService().authenticate("test@example.com", "wrongpassword")
            )
        self.assertEqual(local.call_count, 1)

    def test_login_follows_local_next(self):
        """A relative next URL is honored."""
        response = self.client.post(
            f"{self.login_url}?next=/accounts/profile/",
            {"email": "test@example.com", "password": "testpass123"},
        )
        self.assertRedirects(
            response, "/accounts/profile/", fetch_redirect_response=False
        )

    def test_login_ignores_external_next(self):
        """An external next URL must not become an open redirect."""
        for target in ("https://evil.example.com/", "//evil.example.com/"):
            self.client.logout()
            response = self.client.post(
                f"{self.login_url}?next={target}",
                {"email": "test@example.com", "password": "testpass123"},
            )
            self.assertEqual(response.status_code, 302)
            self.assertNotIn("evil.example.com", response.url)

    def test_authenticated_user_redirected_to_home(self):
        """Test that authenticated users are redirected from login."""
        self.client.login(email="test@example.com", password="testpass123")
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.home_url, response.url)


@override_settings(IDENTITY_SERVICE_URL="http://identity.example.com")
class IdentityServiceModeTests(TestCase):
    """Tests for external identity service mode."""

    def test_backend_delegates_to_identity_service(self):
        """The backend still asks the external service when it is configured."""
        with patch(
            "accounts.services.IdentityServiceClient.login", return_value=None
        ) as login:
            self.assertIsNone(authenticate(username="a@example.com", password="x"))
        login.assert_called_once_with("a@example.com", "x")


class LogoutViewTests(TestCase):
    """Tests for logout view."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.logout_url = reverse("accounts:logout")
        self.login_url = reverse("accounts:login")
        
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
        )

    def test_logout_redirects_to_login(self):
        """Test that logout redirects to login."""
        self.client.login(email="test@example.com", password="testpass123")
        response = self.client.get(self.logout_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.login_url, response.url)


class ProfileViewTests(TestCase):
    """Tests for profile view."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.profile_url = reverse("accounts:profile")
        self.login_url = reverse("accounts:login")
        
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User",
        )

    def test_profile_requires_login(self):
        """Test that profile view requires authentication."""
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.login_url, response.url)

    def test_profile_shows_user_info(self):
        """Test that profile shows user information."""
        self.client.login(email="test@example.com", password="testpass123")
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test User")
        self.assertContains(response, "test@example.com")
