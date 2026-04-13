from .models import UserRole


def can_user_view_customer_data(user):
    """Return True if the user is allowed to see customer PII."""
    if user.is_superuser:
        return True
    try:
        return user.userrole.role.can_view_customer_data
    except (AttributeError, UserRole.DoesNotExist):
        return False
