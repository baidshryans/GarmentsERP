"""Server-side factory scoping (BR-23). Never rely on the UI to hide data."""
from django.core.exceptions import PermissionDenied
from django.db import models

from .exceptions import FactoryNotAllowed


class FactoryScopedQuerySet(models.QuerySet):
    factory_lookup = "factory"

    def for_user(self, user):
        """Only rows in factories the user may see. Anonymous users see nothing."""
        if not user.is_authenticated:
            return self.none()
        ids = user.allowed_factory_ids()
        if ids is None:
            return self.all()
        return self.filter(**{f"{self.factory_lookup}__in": ids})

    def unscoped(self):
        """Explicit opt-out for system jobs. Greppable on purpose."""
        return self.all()


class FactoryScopedModel(models.Model):
    """Abstract base: a row that belongs to exactly one factory."""

    factory = models.ForeignKey("core.Factory", on_delete=models.PROTECT, related_name="+")

    objects = FactoryScopedQuerySet.as_manager()

    class Meta:
        abstract = True


def assert_factory_access(user, factory):
    """Raise FactoryNotAllowed unless the user may post in this factory. None = system job."""
    if user is not None and not user.can_access_factory(factory):
        raise FactoryNotAllowed(f"You do not have access to factory {factory.code}.")


class FactoryScopedViewMixin:
    """For class-based views and DRF viewsets: filters the queryset to the user's factories."""

    def get_queryset(self):
        parent = super()
        qs = parent.get_queryset() if hasattr(parent, "get_queryset") else self.queryset.all()
        return qs.for_user(self.request.user)


class ScreenPermissionMixin:
    """Class-based views: require screen_code + screen_action for the user's roles."""

    screen_code = None
    screen_action = "view"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.has_screen_perm(
            self.screen_code, self.screen_action
        ):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
