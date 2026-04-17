"""
URL configuration for accounts app.

Maps authentication views to URLs.
"""

from django.urls import path

from accounts.views import LoginView, LogoutAllView, LogoutView, ProfileView

app_name = "accounts"

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("logout-all/", LogoutAllView.as_view(), name="logout_all"),
]
