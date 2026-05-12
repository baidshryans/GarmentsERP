from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mastersconfig', '0006_remove_companymaster_gstin'),
    ]

    operations = [
        migrations.AddField(
            model_name='companymaster',
            name='legal_name',
            field=models.CharField(
                blank=True,
                help_text='Legal/registered name of the company (as per MCA/GST records)',
                max_length=200,
            ),
        ),
    ]
