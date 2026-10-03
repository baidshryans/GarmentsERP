"""BRD acceptance scenarios A9 and A12 (section 11.1) as far as release 1 builds them: the month-end reports with no manual
adjustment, and one of each voucher type with the books tallying per factory and combined.

A9's style profitability report is E10.3, which the PRD puts in release 2, so it is not here. A12's stock journal and
payroll are not built yet; every other voucher type is, and job work bills post from job work (test_jobwork.py)."""
from datetime import date, timedelta
from decimal import Decimal

from django.test import Client
from django.urls import reverse

from core.services import yearend
from ledger.models import Ledger
from ledger.selectors import trial_balance
from ledger.services.manual import Row, post_manual_voucher
from ledger.services.party_voucher import PartyRow, post_party_voucher
from masters.services import parties
from reports.services import books, gst
from sales.services import credit_notes
from tax.models import TaxTemplate
from tests import sales_helpers as sh
from tests.test_sales import quick_invoice

D = Decimal
DAY = sh.DAY
FROM, TO = date(2026, 4, 1), date(2027, 3, 31)


def led(company, key):
    return Ledger.objects.get(company=company, system_key=key)


def test_A9_month_end_reports_come_out_without_any_manual_adjustment(company, factory, owner):
    ns = sh.build(company, factory, owner)
    sh.gst_on(company)
    quick_invoice(ns, ns.local, qty="10", rate="500")
    inv = quick_invoice(ns, ns.far, qty="20", rate="600", color="Navy", size="L")
    first = ns.local.sale_invoices.first()
    credit_notes.post_credit_note(credit_notes.save_credit_note(
        invoice=first, location=ns.godown, date=DAY, user=owner, lines=[(first.lines.get(), D("2"))], reason="Return"), user=owner)
    post_manual_voucher(company=company, factory=factory, vtype="journal", on_date=DAY, narration="Rent", header={}, user=owner, rows=[
        Row(ledger=str(led(company, "factory_rent").pk), debit="3000"), Row(ledger=str(led(company, "cash").pk), credit="3000")])
    c = Client()
    c.force_login(owner)
    tb = trial_balance(company, user=owner)
    assert tb["tallies"] and tb["total_debit"] > 0
    pl = books.profit_and_loss(company, user=owner, date_from=FROM, date_to=TO)
    assert pl["sales"] == D("16000.00")                                           # 5,000 + 12,000 sold, 1,000 returned
    cogs_net = D("9000.00") - D("600.00")                                          # 30 pieces at 300, 2 came back
    assert pl["trading_income"] == D("16000.00") and pl["trading_expense"] == cogs_net + D("3000.00")   # factory rent is a direct expense
    assert pl["gross_profit"] == pl["net_profit"] == D("4600.00")                  # 16,000 - 8,400 cost - 3,000 rent
    bs = books.balance_sheet(company, user=owner, as_of=TO)
    assert bs["tallies"] and bs["current_profit"] == pl["net_profit"]
    r1 = gst.gstr1(company, user=owner, date_from=FROM, date_to=TO)
    r3 = gst.gstr3b(company, user=owner, date_from=FROM, date_to=TO)
    assert (r1["totals"]["igst"], r1["totals"]["cgst"], r1["totals"]["sgst"]) == (D("600.00"), D("100.00"), D("100.00"))
    assert r3["output"] == {"igst": D("600.00"), "cgst": D("100.00"), "sgst": D("100.00")}      # the two returns agree to the paisa
    assert r1["totals"]["taxable"] == D("16000.00")
    for name in ("trial_balance", "profit_loss", "balance_sheet", "gstr1", "gstr3b", "tax_register", "day_book"):
        assert c.get(reverse(name)).status_code == 200, name
    assert inv.number in c.get(reverse("gstr1")).content.decode()


def test_A12_one_of_each_voucher_type_and_every_factory_tallies_alone_and_combined(company, factory, factory2, owner):
    ns = sh.build(company, factory, owner)
    sh.gst_on(company)
    vendor = parties.create_party(company=company, name="Yarn House", mobile="9833333333", is_vendor=True)
    cash, bank_group = led(company, "cash"), None
    from ledger.models import AccountGroup

    bank = Ledger.objects.create(company=company, group=AccountGroup.objects.get(company=company, name="Bank Accounts"), name="HDFC Current")
    posted = []
    for fac in (factory, factory2):
        h = {"account": str(cash.pk)}
        posted.append(post_manual_voucher(company=company, factory=fac, vtype="journal", on_date=DAY, narration="Rent", header={}, user=owner, rows=[
            Row(ledger=str(led(company, "factory_rent").pk), debit="1000"), Row(ledger=str(cash.pk), credit="1000")]))
        posted.append(post_manual_voucher(company=company, factory=fac, vtype="contra", on_date=DAY, narration="Deposit", user=owner, rows=[],
                                          header={"from_account": str(cash.pk), "to_account": str(bank.pk), "amount": "500"}))
        posted.append(post_manual_voucher(company=company, factory=fac, vtype="payment", on_date=DAY, narration="Power", user=owner,
                                          header={"account": str(bank.pk)}, rows=[Row(ledger=str(led(company, "power_fuel").pk), amount="200")]))
        posted.append(post_manual_voucher(company=company, factory=fac, vtype="receipt", on_date=DAY, narration="Scrap", user=owner,
                                          header={"account": str(bank.pk)}, rows=[Row(ledger=str(led(company, "scrap_sales").pk), amount="300")]))
        ref = fac.code
        posted.append(post_party_voucher(company=company, factory=fac, vtype="purchase", on_date=DAY, party=vendor.payable_ledger.pk, user=owner,
                                         rows=[PartyRow(ledger=str(led(company, "purchases_fabric").pk), amount="4000")], reference=f"P-{ref}",
                                         gst_template=TaxTemplate.objects.get(name="GST 12% intra-state (CGST + SGST)")))
        posted.append(post_party_voucher(company=company, factory=fac, vtype="debit_note", on_date=DAY, party=vendor.payable_ledger.pk, user=owner,
                                         rows=[PartyRow(ledger=str(led(company, "purchase_returns").pk), amount="400")], reference=f"P-{ref}"))
        posted.append(post_party_voucher(company=company, factory=fac, vtype="sales", on_date=DAY, party=ns.local.customer_ledger.pk, user=owner,
                                         rows=[PartyRow(ledger=str(led(company, "sales_stock").pk), amount="2500")], reference=f"S-{ref}"))
        posted.append(post_party_voucher(company=company, factory=fac, vtype="credit_note", on_date=DAY, party=ns.local.customer_ledger.pk, user=owner,
                                         rows=[PartyRow(ledger=str(led(company, "sales_returns").pk), amount="250")], reference=f"S-{ref}"))
    quick_invoice(ns, ns.local, qty="4", rate="500")                                     # an automatic sales voucher as well
    assert {v.voucher_type for v in posted} == {"journal", "contra", "payment", "receipt", "purchase", "debit_note", "sales", "credit_note"}
    combined_pl = books.profit_and_loss(company, user=owner, date_from=FROM, date_to=TO)
    parts = [books.profit_and_loss(company, user=owner, factory=f, date_from=FROM, date_to=TO) for f in (factory, factory2)]
    assert combined_pl["net_profit"] == sum((p["net_profit"] for p in parts), D("0.00"))
    for f in (factory, factory2, None):
        tb = trial_balance(company, user=owner, factory=f)
        assert tb["tallies"], f
        assert books.balance_sheet(company, user=owner, factory=f, as_of=TO)["tallies"], f
    nets = [books.balance_sheet(company, user=owner, factory=f, as_of=TO)["assets_total"] for f in (factory, factory2)]
    assert books.balance_sheet(company, user=owner, as_of=TO)["assets_total"] == sum(nets, D("0.00"))
    yearend.close_year(user=owner, company=company, financial_year=company.financial_years.get(label="26-27"))
    assert books.balance_sheet(company, user=owner, as_of=date(2027, 4, 30))["tallies"]       # still balances after closing the year
