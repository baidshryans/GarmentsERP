from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0009_salesapprovalitem_making'),
    ]

    operations = [
        migrations.AddField(
            model_name='salesapprovalitem',
            name='making_type',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
        migrations.AddField(
            model_name='salesapprovalitem',
            name='making_value',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
    ]
