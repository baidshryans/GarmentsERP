from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0004_add_purity_to_barcode_details'),
    ]

    operations = [
        # BarcodeMain.nw: 2 → 3 decimal places
        migrations.AlterField(
            model_name='barcodemain',
            name='nw',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True),
        ),
        # UnBarcodedMain.nw: 2 → 3 decimal places
        migrations.AlterField(
            model_name='unbarcodedmain',
            name='nw',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True),
        ),
        # OpeningInventory.ct: 2 → 3 decimal places
        migrations.AlterField(
            model_name='openinginventory',
            name='ct',
            field=models.DecimalField(decimal_places=3, max_digits=10),
        ),
    ]
