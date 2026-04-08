from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mastersconfig', '0004_add_sale_discount_ldgr'),
    ]

    operations = [
        # 1. Add fields to CompanyMaster
        migrations.AddField(
            model_name='companymaster',
            name='max_cash_receipt_limit',
            field=models.DecimalField(
                decimal_places=2, default=199999, max_digits=12,
                help_text='Maximum cash receivable from a single customer per financial year (Sec 269ST)',
            ),
        ),
        migrations.AddField(
            model_name='companymaster',
            name='max_cash_payment_limit',
            field=models.DecimalField(
                decimal_places=2, default=10000, max_digits=12,
                help_text='Maximum cash payable to a single party in a single day (Sec 40A(3))',
            ),
        ),
        # 2. Remove fields from RetailMaster
        migrations.RemoveField(
            model_name='retailmaster',
            name='max_cash_receipt_limit',
        ),
        migrations.RemoveField(
            model_name='retailmaster',
            name='max_cash_payment_limit',
        ),
    ]
