"""Backfill the new config FKs from the existing named system ledgers.

Links CompanyMaster.cheques_in_hand_ldgr / gold_scheme_liability_ldgr and
RetailMaster.sales_incentive_ldgr to the ledgers that were previously resolved
by name, so write paths can reference them by id. No-ops where the source
ledger doesn't exist.
"""
from django.db import migrations


def link_fks(apps, schema_editor):
    CompanyMaster = apps.get_model("mastersconfig", "CompanyMaster")
    RetailMaster = apps.get_model("mastersconfig", "RetailMaster")
    Ledger = apps.get_model("contacts", "Ledger")

    cheques = Ledger.objects.filter(ac_name="Cheques in Hand", is_system=True).first()
    scheme = Ledger.objects.filter(ac_name="Gold Scheme Liability", is_system=True).first()
    for company in CompanyMaster.objects.all():
        fields = []
        if cheques and company.cheques_in_hand_ldgr_id is None:
            company.cheques_in_hand_ldgr = cheques
            fields.append("cheques_in_hand_ldgr")
        if scheme and company.gold_scheme_liability_ldgr_id is None:
            company.gold_scheme_liability_ldgr = scheme
            fields.append("gold_scheme_liability_ldgr")
        if fields:
            company.save(update_fields=fields)

    for retail in RetailMaster.objects.all():
        if retail.sales_incentive_ldgr_id is not None:
            continue
        incentive = Ledger.objects.filter(
            ac_name="Sales Incentive", retail_code=retail
        ).first()
        if incentive:
            retail.sales_incentive_ldgr = incentive
            retail.save(update_fields=["sales_incentive_ldgr"])


class Migration(migrations.Migration):
    dependencies = [
        ("mastersconfig", "0005_companymaster_cheques_in_hand_ldgr_and_more"),
    ]
    operations = [migrations.RunPython(link_fks, migrations.RunPython.noop)]
