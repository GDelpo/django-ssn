import logging
from typing import Any, Optional

from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.messages import error, success
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import FormView, View

from accounts.forms import LoginForm
from accounts.middleware import LoginRequiredMixin
from accounts.services import AuthenticationService

logger = logging.getLogger("accounts")


class LoginView(FormView):
    """
    View for user login.

    Supports both local authentication and external identity service.
    """

    template_name = "accounts/login.html"
    form_class = LoginForm
    success_url = reverse_lazy("theme:index")

    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """Redirect authenticated users to home."""
        if request.user.is_authenticated:
            return redirect(self.success_url)

        return super().get(request, *args, **kwargs)

    def form_valid(self, form) -> HttpResponseRedirect:
        """
        Authenticate user and create session.

        Uses AuthenticationService which handles both local and identity service auth.
        """
        email = form.cleaned_data.get("email")
        password = form.cleaned_data.get("password")
        remember_me = form.cleaned_data.get("remember_me", False)

        try:
            # Use AuthenticationService for flexible auth
            auth_service = AuthenticationService()
            user = auth_service.authenticate(email, password)

            if user:
                # Log the user in
                login(self.request, user)

                # Set session expiration based on remember_me
                if remember_me:
                    self.request.session.set_expiry(
                        7 * 24 * 60 * 60
                    )  # 7 days
                    logger.info(f"✅ User {email} logged in with 'remember me'")
                else:
                    self.request.session.set_expiry(
                        30 * 60
                    )  # 30 minutes
                    logger.info(f"✅ User {email} logged in")

                success(self.request, f"¡Bienvenido de regreso, {user.get_short_name()}!")

                # Redirect to next page or home
                next_page = self.request.GET.get("next", self.success_url)
                return redirect(next_page)
            else:
                # Authentication failed
                logger.warning(f"❌ Authentication failed for {email}")
                error(self.request, "Email o contraseña incorrectos. Por favor, intenta de nuevo.")
                return super().form_invalid(form)

        except Exception as e:
            logger.error(f"Login error for {email}: {e}")
            error(self.request, "Error durante la autenticación. Intenta de nuevo.")

        return super().form_invalid(form)

    def form_invalid(self, form) -> HttpResponse:
        """Handle invalid form submission."""
        for field, errors in form.errors.items():
            for error_msg in errors:
                error(self.request, error_msg)

        return super().form_invalid(form)

    def get_context_data(self, **kwargs: Any) -> dict:
        """Add additional context for the template."""
        context = super().get_context_data(**kwargs)
        context["use_identity_service"] = bool(
            getattr(settings, "IDENTITY_SERVICE_URL", "").strip()
        )
        context["page_title"] = "Iniciar Sesión"
        context["support_email"] = getattr(
            settings, "SUPPORT_EMAIL", "soporte@compania.com"
        )
        return context


class LogoutView(View):
    """View for user logout."""

    def get(self, request: HttpRequest) -> HttpResponseRedirect:
        """Logout user and clear session."""
        if request.user.is_authenticated:
            user_email = request.user.email
            logout(request)
            logger.info(f"✅ User {user_email} logged out")
            success(request, "Sesión cerrada correctamente.")
        else:
            logger.warning("Logout attempt from unauthenticated user")

        return redirect("accounts:login")


class ProfileView(LoginRequiredMixin, View):
    """View for user profile."""

    def get(self, request: HttpRequest) -> HttpResponse:
        """Display user profile."""
        context = {
            "page_title": "Mi Perfil",
            "user": request.user,
        }
        return render(request, "accounts/profile.html", context)


class LogoutAllView(LoginRequiredMixin, View):
    """
    Logout from all devices (invalidate all sessions).

    Note: This is a placeholder. Implementing true multi-device logout would require:
    - Token blacklisting
    - Session invalidation across all devices
    - Permission checks
    """

    def post(self, request: HttpRequest) -> HttpResponseRedirect:
        """Logout from all devices."""
        user_email = request.user.email
        logout(request)
        logger.info(f"✅ User {user_email} logged out from all devices")
        success(request, "Sesión cerrada en todos los dispositivos.")
        return redirect("accounts:login")
