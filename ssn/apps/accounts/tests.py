"""
Tests for accounts app.

Test authentication, user creation, and views.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse

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
        self.assertFormError(
            response,
            "form",
            None,
            "Email o contraseña incorrectos. Por favor, intenta de nuevo.",
        )

    def test_authenticated_user_redirected_to_home(self):
        """Test that authenticated users are redirected from login."""
        self.client.login(email="test@example.com", password="testpass123")
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.home_url, response.url)


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
