from django.db import migrations


def add_cogs(apps, schema_editor):
    """Companies set up before sales existed get the Cost of Goods Sold ledger that invoices post to."""
    Company = apps.get_model("core", "Company")
    Group = apps.get_model("ledger", "AccountGroup")
    Ledger = apps.get_model("ledger", "Ledger")
    for company in Company.objects.all():
        group = Group.objects.filter(company=company, name="Direct Expenses").first()
        if group is None or Ledger.objects.filter(company=company, system_key="cogs").exists():
            continue
        Ledger.objects.get_or_create(company=company, name="Cost of Goods Sold",
                                     defaults={"group": group, "system_key": "cogs", "is_system": True})


class Migration(migrations.Migration):
    dependencies = [("sales", "0001_initial"), ("ledger", "0002_voucher_vendor_invoice_no"), ("core", "0004_company_bom_tolerance_pct_and_more")]
    operations = [migrations.RunPython(add_cogs, migrations.RunPython.noop)]
