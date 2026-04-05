from django.db import models
from django.utils import timezone

# Create your models here.

class PurityMaster(models.Model):
    purity = models.CharField(max_length = 10)
    gw_per = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = "purity_master"

class GoldRates(models.Model):
    date1 = models.DateTimeField(auto_now_add=True)
    purity = models.ForeignKey(PurityMaster, on_delete = models.SET_NULL, null=True)
    rate = models.IntegerField()
    class Meta:
        db_table = "gold_rates"
    
    @property
    def purity_name(self):
        return self.purity.purity if self.purity else None
    