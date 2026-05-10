from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework.authtoken.models import Token

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.contrib.contenttypes.models import ContentType

# class Location(models.Model):
#     location = models.CharField(max_length=255) 


# class LocationUser(AbstractUser):
#     location = models.ForeignKey(Location,on_delete=models.SET_NULL,related_name="user_location",null=True)

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_auth_token(sender, instance=None, created=False, **kwargs):
    if created:
        Token.objects.create(user=instance)

class Role(models.Model):
    name = models.CharField(max_length=100, unique=True)
    can_view_customer_data = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class Permission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='permissions')
    module = models.ForeignKey(ContentType, on_delete=models.CASCADE,related_name='access_control_permissions')
    can_get = models.BooleanField(default=False)
    can_list = models.BooleanField(default=False)
    can_post = models.BooleanField(default=False)
    can_put = models.BooleanField(default=False)
    can_patch = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.role} {self.module} "



class UserRole(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('user', 'role')


class LoginLog(models.Model):
    """Records every login attempt and explicit logout for the main ERP app."""
    ACTION_CHOICES = [('login', 'Login'), ('logout', 'Logout')]

    user                = models.ForeignKey(
                            settings.AUTH_USER_MODEL,
                            null=True, blank=True,
                            on_delete=models.SET_NULL,
                            related_name='login_logs',
                          )
    username_attempted  = models.CharField(max_length=150, blank=True)  # captures failed-login usernames
    action              = models.CharField(max_length=10, choices=ACTION_CHOICES)
    success             = models.BooleanField(default=True)
    ip_address          = models.GenericIPAddressField(null=True, blank=True)
    user_agent          = models.CharField(max_length=500, blank=True)
    timestamp           = models.DateTimeField(auto_now_add=True, db_index=True)
    retail              = models.ForeignKey(
                            'mastersconfig.RetailMaster',
                            null=True, blank=True,
                            on_delete=models.SET_NULL,
                          )

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.action} {self.username_attempted or (self.user.username if self.user else '?')} @ {self.timestamp}"