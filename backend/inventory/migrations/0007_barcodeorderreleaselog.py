from django.conf import settings
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0006_unbarcodedmain_source_barcode_and_more"),
        ("sales", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BarcodeOrderReleaseLog",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("original_order_no", models.CharField(blank=True, max_length=50)),
                ("mode", models.CharField(choices=[("cancel_order", "Cancel original order"), ("reassign", "Release - order stays open")], max_length=20)),
                ("remarks", models.TextField(blank=True)),
                ("released_at", models.DateTimeField(auto_now_add=True)),
                ("barcode", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="order_release_logs", to="inventory.barcodemain")),
                ("original_order", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="sales.customerorder")),
                ("released_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "barcode_order_release_log",
                "ordering": ["-released_at"],
            },
        ),
    ]
