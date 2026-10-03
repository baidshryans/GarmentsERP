from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .models import AuditEvent, User


def _ip(request):
    return request.META.get("REMOTE_ADDR") if request else None


@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    AuditEvent.objects.create(user=user, username=user.get_username(), event="login", ip_address=_ip(request))


@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):
    if user is not None:
        AuditEvent.objects.create(
            user=user, username=user.get_username(), event="logout", ip_address=_ip(request)
        )


@receiver(user_login_failed)
def on_failed(sender, credentials, request=None, **kwargs):
    username = credentials.get("username", "")
    user = User.objects.filter(username__iexact=username).first()
    event = "locked" if user and user.is_locked() else "failed"
    AuditEvent.objects.create(user=user, username=username, event=event, ip_address=_ip(request))
