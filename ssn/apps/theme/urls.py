from django.urls import path

from .views import HomeView, ssn_status

app_name = "theme"

urlpatterns = [
    path("", HomeView.as_view(), name="index"),
    path("ssn-status/", ssn_status, name="ssn_status"),
]
