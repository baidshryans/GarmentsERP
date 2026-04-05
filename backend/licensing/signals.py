from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import AppLicense, CompanySubscription


@receiver(post_save, sender=CompanySubscription)
@receiver(post_delete, sender=CompanySubscription)
def invalidate_subscription_cache(sender, instance, **kwargs):
    cache.delete(f"company_license_{instance.company_id}")


@receiver(post_save, sender=AppLicense)
@receiver(post_delete, sender=AppLicense)
def invalidate_license_cache(sender, instance, **kwargs):
    cache.delete(f"company_license_{instance.subscription.company_id}")
