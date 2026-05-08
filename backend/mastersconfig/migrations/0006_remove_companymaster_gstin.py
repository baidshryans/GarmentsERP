from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('mastersconfig', '0005_companymaster_bis_logo_companymaster_company_logo'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='companymaster',
            name='gstin',
        ),
    ]
