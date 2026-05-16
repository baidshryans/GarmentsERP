from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0004_sale_old_gold_adjustment'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='salesapprovalitemdetails',
            name='tunch',
        ),
    ]
