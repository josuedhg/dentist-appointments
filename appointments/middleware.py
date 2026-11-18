from django.shortcuts import redirect
from django.urls import reverse

from .models import DentistProfile, PatientProfile


class ForcePasswordChangeMiddleware:
    """Send anyone with a temporary or invited password to the setup screen
    before they can use the rest of the site."""

    allowed_prefixes = ("/admin/", "/static/", "/media/", "/api/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            path = request.path
            if not path.startswith(self.allowed_prefixes):
                if DentistProfile.objects.filter(
                    user=user, must_change_password=True
                ).exists():
                    dentist_allowed = {
                        reverse(name) for name in ("password-change", "login", "logout")
                    }
                    if path not in dentist_allowed:
                        return redirect("password-change")
                elif PatientProfile.objects.filter(
                    user=user, must_change_password=True
                ).exists():
                    patient_allowed = {
                        reverse(name) for name in ("password-setup", "login", "logout")
                    }
                    if path not in patient_allowed:
                        return redirect("password-setup")
        return self.get_response(request)
