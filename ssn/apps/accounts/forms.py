"""
Forms for authentication.

Login and registration forms using Django forms with Tailwind styling.
Uses the shared form styles from operaciones.helpers.form_styles for consistency.
"""

import logging

from django import forms
from django.contrib.auth import get_user_model

from operaciones.helpers.form_styles import apply_tailwind_style, CLASS_INPUT, CLASS_CHECKBOX

logger = logging.getLogger("accounts")
User = get_user_model()

# Custom input class for login form with icon padding
CLASS_INPUT_WITH_ICON = f"{CLASS_INPUT} pl-10"


class LoginForm(forms.Form):
    """Form for user login."""

    email = forms.EmailField(
        label="Email",
        max_length=254,
        widget=forms.EmailInput(
            attrs={
                "placeholder": "ejemplo@empresa.com",
                "autocomplete": "email",
            }
        ),
    )

    password = forms.CharField(
        label="Contraseña",
        max_length=128,
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "••••••••",
                "autocomplete": "current-password",
            }
        ),
    )

    remember_me = forms.BooleanField(
        label="Recuérdame en este dispositivo",
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Apply shared Tailwind styles
        apply_tailwind_style(self.fields)
        # Override with icon-compatible padding for email and password
        self.fields["email"].widget.attrs["class"] = CLASS_INPUT_WITH_ICON
        self.fields["password"].widget.attrs["class"] = CLASS_INPUT_WITH_ICON

    def clean(self):
        """Validate the form fields (no authentication here)."""
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        password = cleaned_data.get("password")

        if not email:
            raise forms.ValidationError("El email es requerido.")
        if not password:
            raise forms.ValidationError("La contraseña es requerida.")

        return cleaned_data


class LocalUserCreationForm(forms.ModelForm):
    """Form for creating local users (admin only)."""

    password1 = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(),
    )
    password2 = forms.CharField(
        label="Confirmar Contraseña",
        widget=forms.PasswordInput(),
    )

    class Meta:
        model = User
        fields = ("email", "first_name", "last_name")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Apply shared Tailwind styles
        apply_tailwind_style(self.fields)

    def clean_password2(self):
        """Validate that passwords match."""
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Las contraseñas no coinciden.")

        return password2

    def save(self, commit=True):
        """Save the user with hashed password."""
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])

        if commit:
            user.save()

        return user
