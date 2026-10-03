from django.db import migrations


def add_ledger(apps, schema_editor):
    """Companies set up earlier get the Stock Adjustments ledger that stock journals post their gain or loss to."""
    Company = apps.get_model("core", "Company")
    Group = apps.get_model("ledger", "AccountGroup")
    Ledger = apps.get_model("ledger", "Ledger")
    for company in Company.objects.all():
        group = Group.objects.filter(company=company, name="Indirect Expenses").first()
        if group is None or Ledger.objects.filter(company=company, system_key="stock_adjustment").exists():
            continue
        Ledger.objects.get_or_create(company=company, name="Stock Adjustments",
                                     defaults={"group": group, "system_key": "stock_adjustment", "is_system": True})


class Migration(migrations.Migration):
    dependencies = [("inventory", "0004_stockjournal"), ("ledger", "0002_voucher_vendor_invoice_no"), ("core", "0004_company_bom_tolerance_pct_and_more")]
    operations = [migrations.RunPython(add_ledger, migrations.RunPython.noop)]
