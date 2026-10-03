from datetime import timedelta

from django.conf import settings
from django.contrib.auth.backends import ModelBackend
from django.utils import timezone

from .models import User


class LockoutBackend(ModelBackend):
    """Username + password with lockout after repeated failures (NFR-02). No OTP login."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        user = User.objects.filter(username__iexact=username).first()
        if user is None:
            User().set_password(password)  # equalise timing
            return None
        if user.is_locked():
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            if user.failed_logins:
                User.objects.filter(pk=user.pk).update(failed_logins=0, locked_until=None)
            return user
        failures = user.failed_logins + 1
        update = {"failed_logins": failures}
        if failures >= settings.LOGIN_MAX_FAILURES:
            update["locked_until"] = timezone.now() + timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
            update["failed_logins"] = 0
        User.objects.filter(pk=user.pk).update(**update)
        return None
