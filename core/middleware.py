from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import urlencode

from .models import Company
from .services import active_factory


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


class ActiveFactoryMiddleware:
    """Sets request.factory (the one factory in use, or None), request.factory_all ("All factories" mode)
    and request.active_factories (the factories every list and report is limited to).

    A user who has several factories and has not chosen one yet is sent to the picker.
    """

    OPEN_PREFIXES = ("/static/", "/setup/", "/factory/", "/admin/", "/api/", "/accounts/login/", "/accounts/logout/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.factory, request.factory_all, request.active_factories = None, False, []
        user = request.user
        if user.is_authenticated:
            factory, is_all, needs_choice = active_factory.resolve(request)
            request.factory, request.factory_all = factory, is_all
            if factory:
                request.active_factories = [factory]
            elif is_all:
                request.active_factories = list(active_factory.allowed_factories(user))
            elif needs_choice and not request.path.startswith(self.OPEN_PREFIXES):
                return redirect(f"{reverse('factory_select')}?{urlencode({'next': request.get_full_path()})}")
        return self.get_response(request)
