# Generated for adding making charge field to SalesApprovalItem.
# Without this column the frontend's per-row "Making" input is lost on save
# and the field appears blank when re-opening the approval in edit mode.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0008_sales_approval_return'),
    ]

    operations = [
        migrations.AddField(
            model_name='salesapprovalitem',
            name='making',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
    ]
