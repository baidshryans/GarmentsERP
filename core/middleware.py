from django.shortcuts import redirect
from django.urls import reverse

from .models import Company


class SetupRequiredMiddleware:
    """Until the wizard has finished nothing else is reachable (E1.1: cannot be skipped)."""

    OPEN_PREFIXES = ("/static/", "/setup/", "/accounts/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith(self.OPEN_PREFIXES) and not request.path.startswith("/admin/"):
            if not Company.objects.filter(setup_complete=True).exists():
                return redirect(reverse("setup"))
        return self.get_response(request)
