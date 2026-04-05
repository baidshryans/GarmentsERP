from django.db import models


class AppRegistry(models.Model):
    """
    Master catalog of all available ERP modules.
    Populated by the vendor; extended when new apps (HR, etc.) are built.
    """
    code             = models.CharField(max_length=30, unique=True, help_text='Unique app code, e.g. "sales", "hr"')
    name             = models.CharField(max_length=100, help_text='Display name, e.g. "Sales & Billing"')
    description      = models.TextField(blank=True)
    django_app_label = models.CharField(max_length=50, help_text='Must match the Django app label in INSTALLED_APPS')
    icon             = models.CharField(max_length=50, blank=True, help_text='Lucide icon name for frontend')
    monthly_price    = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_core          = models.BooleanField(default=False, help_text='Core apps (contacts, masters, auth) are always active')
    depends_on       = models.ManyToManyField('self', symmetrical=False, blank=True, help_text='Apps this module requires')
    sort_order       = models.PositiveIntegerField(default=0)
    is_active        = models.BooleanField(default=True, help_text='Vendor can retire an app')
    nav_group_keys   = models.JSONField(default=list, blank=True, help_text='Frontend nav keys, e.g. ["navMain2"]')

    class Meta:
        db_table = 'app_registry'
        ordering = ['sort_order']
        verbose_name = 'App'
        verbose_name_plural = 'App Registry'

    def __str__(self):
        return f"{self.name} ({self.code})"


class CompanySubscription(models.Model):
    """
    Top-level subscription record per company.
    Controls the overall validity window and resource limits.
    """
    STATUS_CHOICES = [
        ('trial', 'Trial'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('suspended', 'Suspended'),
    ]
    company      = models.OneToOneField(
        'mastersconfig.CompanyMaster', on_delete=models.CASCADE, related_name='subscription'
    )
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default='trial')
    start_date   = models.DateField()
    end_date     = models.DateField()
    max_users    = models.PositiveIntegerField(default=5)
    max_retails  = models.PositiveIntegerField(default=1)
    notes        = models.TextField(blank=True, help_text='Vendor internal notes')
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'company_subscription'
        verbose_name = 'Company Subscription'

    def __str__(self):
        return f"{self.company} — {self.status} (until {self.end_date})"


class AppLicense(models.Model):
    """
    Join table: Company X has access to App Y.
    """
    subscription = models.ForeignKey(
        CompanySubscription, on_delete=models.CASCADE, related_name='licenses'
    )
    app          = models.ForeignKey(
        AppRegistry, on_delete=models.CASCADE, related_name='licenses'
    )
    is_enabled   = models.BooleanField(default=True)
    licensed_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'app_license'
        unique_together = ('subscription', 'app')
        verbose_name = 'App License'

    def __str__(self):
        status = "enabled" if self.is_enabled else "disabled"
        return f"{self.subscription.company} → {self.app.name} ({status})"
