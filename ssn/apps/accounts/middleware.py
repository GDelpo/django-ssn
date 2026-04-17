"""
Middleware and decorators for authentication protection.

Provides login_required decorator, permission checks, and middleware for auth.
"""

import logging
from functools import wraps
from typing import Callable

from django.contrib.auth.decorators import login_required as django_login_required
from django.http import HttpRequest, HttpResponseRedirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.generic import View

logger = logging.getLogger("accounts")


def login_required(
    view_func: Callable = None,
    redirect_url: str = "accounts:login",
) -> Callable:
    """
    Decorator to require authentication for a view.

    Usage:
        @login_required
        def my_view(request):
            ...

        @login_required(redirect_url='accounts:login')
        def my_view(request):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            if not request.user.is_authenticated:
                return HttpResponseRedirect(
                    f"{reverse(redirect_url)}?next={request.path}"
                )
            return func(request, *args, **kwargs)

        return wrapper

    if view_func is None:
        return decorator
    else:
        return decorator(view_func)


def permission_required(permission: str) -> Callable:
    """
    Decorator to require a specific permission.

    Usage:
        @permission_required('accounts.change_user')
        def my_view(request):
            ...
    """

    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            if not request.user.is_authenticated:
                return HttpResponseRedirect(f"{reverse('accounts:login')}?next={request.path}")

            if not request.user.has_perm(permission):
                from django.http import HttpResponseForbidden

                return HttpResponseForbidden("Permiso denegado")

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def role_required(role: str) -> Callable:
    """
    Decorator to require a specific role.

    Note: Requires is_staff or is_superuser. Extend as needed for custom roles.

    Usage:
        @role_required('admin')
        def my_view(request):
            ...
    """

    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            if not request.user.is_authenticated:
                return HttpResponseRedirect(f"{reverse('accounts:login')}?next={request.path}")

            roles_map = {
                "admin": request.user.is_superuser,
                "staff": request.user.is_staff,
            }

            has_role = roles_map.get(role, False)

            if not has_role:
                from django.http import HttpResponseForbidden

                return HttpResponseForbidden(f"Rol '{role}' requerido")

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


class LoginRequiredMixin:
    """Mixin for class-based views to require authentication."""

    @method_decorator(django_login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class PermissionRequiredMixin:
    """Mixin for class-based views to require a specific permission."""

    permission_required = None

    def dispatch(self, request, *args, **kwargs):
        if self.permission_required and not request.user.has_perm(self.permission_required):
            from django.http import HttpResponseForbidden

            return HttpResponseForbidden("Permiso denegado")

        return super().dispatch(request, *args, **kwargs)
