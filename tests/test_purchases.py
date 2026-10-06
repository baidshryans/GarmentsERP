from datetime import date, timedelta
from decimal import Decimal

import pytest

from core.exceptions import BusinessRuleError, FactoryNotAllowed
from core.models import Location
from inventory.models import FabricRoll, StockBalance, StockMovement
from inventory.services import stock
from ledger.models import Voucher
from ledger.selectors import ledger_balance, outstanding_bills
from masters.models import Material, Unit
from masters.services import parties
from purchases.models import DebitNote, Grn, PurchaseOrder
from purchases.services import debit_notes, grn as grns, invoices, orders
from tax.models import TaxTemplate
from tests.conftest import make_user

D = Decimal
DAY = date(2026, 6, 15)
GST12 = "GST 12% intra-state (CGST + SGST)"


@pytest.fixture
def vendor(company):
    return parties.create_party(company=company, name="Yarn House", mobile="9833333333", is_vendor=True, credit_days=30)


@pytest.fixture
def godown(factory):
    return Location.objects.get(factory=factory, name="Main Godown")


@pytest.fixture
def fabric(db):
    return Material.objects.create(code="FAB-1", name="Fleece", kind="fabric", unit=Unit.objects.get(code="KG"))


@pytest.fixture
def trim(db):
    return Material.objects.create(code="ZIP-1", name="Zipper", kind="trim", unit=Unit.objects.get(code="PCS"))


def bal(company, key, factory=None):
    from ledger.models import Ledger

    return ledger_balance(Ledger.objects.get(company=company, system_key=key), factory=factory)


def tpl(name):
    return TaxTemplate.objects.get(name=name)


def fabric_grn(company, factory, vendor, godown, fabric, owner, rolls=None, rate="200", po=None, po_line=None):
    rolls = rolls or [("R1", "100", "accepted"), ("R2", "80", "accepted"), ("R3", "20", "rejected")]
    spec = grns.GrnLineSpec(
        item=fabric, rate=D(rate), po_line=po_line,
        rolls=[grns.RollSpec(no, D(q), lot_no="LOT-7", gsm=280, qc_status=qc, remark="ok" if qc == "accepted_remark" else "")
               for no, q, qc in rolls],
    )
    g = grns.create_grn(company=company, factory=factory, location=godown, vendor=vendor, date=DAY, lines=[spec],
                        user=owner, po=po)
    grns.finish_qc(g, user=owner)
    return grns.post_grn(g, user=owner)


def trim_grn(company, factory, vendor, godown, trim, owner, qty="100", rejected="0", rate="10", remark=""):
    spec = grns.GrnLineSpec(item=trim, rate=D(rate), qty_received=D(qty), qty_rejected=D(rejected), remark=remark)
    g = grns.create_grn(company=company, factory=factory, location=godown, vendor=vendor, date=DAY, lines=[spec], user=owner)
    grns.finish_qc(g, user=owner)
    return grns.post_grn(g, user=owner)


def bill(company, factory, vendor, owner, grn_line, qty, rate, no="V-1", **kw):
    inv = invoices.save_invoice(
        company=company, factory=factory, vendor=vendor, vendor_invoice_no=no, vendor_invoice_date=DAY, date=DAY,
        lines=[invoices.InvoiceLineSpec(grn_line, D(qty), D(rate))], user=owner, **kw)
    return invoices.post_invoice(inv, user=owner)


# ============================== purchase orders (E5.1) ==============================

def make_po(company, factory, vendor, owner, item, qty="100", rate="100"):
    po = orders.create_po(company=company, factory=factory, vendor=vendor, date=DAY, user=owner,
                          lines=[orders.POLineSpec(item, D(qty), D(rate))])
    return orders.submit_po(po, user=owner)


def test_po_under_the_limit_is_approved_at_once_and_numbered(company, factory, vendor, owner, trim):
    po = make_po(company, factory, vendor, owner, trim, "100", "100")  # 10,000
    assert po.status == "approved" and po.number == "PO/LDH1/26-27/0001"


def test_po_over_the_limit_waits_for_the_owner_and_cannot_be_received(company, factory, vendor, owner, accountant, godown, trim):
    po = make_po(company, factory, vendor, owner, trim, "1000", "100")  # 100,000 > 50,000
    assert po.status == "pending_approval"
    with pytest.raises(BusinessRuleError, match="not open for receipt"):
        grns.create_grn(company=company, factory=factory, location=godown, vendor=vendor, date=DAY, user=owner, po=po,
                        lines=[grns.GrnLineSpec(item=trim, rate=D("100"), qty_received=D("10"))])
    with pytest.raises(BusinessRuleError, match="owner"):
        orders.approve_po(po, user=accountant)
    po = orders.approve_po(po, user=owner)
    assert po.status == "approved" and po.approved_by == owner


def test_po_limit_is_a_company_setting(company, factory, vendor, owner, trim):
    company.po_approval_limit = D("5000")
    company.save()
    assert make_po(company, factory, vendor, owner, trim, "100", "100").status == "pending_approval"


def test_po_can_be_sent_back_with_a_reason_and_edited_only_as_a_draft(company, factory, vendor, owner, trim):
    po = make_po(company, factory, vendor, owner, trim, "1000", "100")
    with pytest.raises(BusinessRuleError):
        orders.update_po(po, lines=[orders.POLineSpec(trim, D("1"), D("1"))], user=owner)
    with pytest.raises(BusinessRuleError):
        orders.reject_po(po, user=owner, reason=" ")
    po = orders.reject_po(po, user=owner, reason="Rate too high")
    orders.update_po(po, lines=[orders.POLineSpec(trim, D("10"), D("100"))], user=owner)


def test_po_receipt_tracks_ordered_vs_received_and_closes(company, factory, vendor, owner, godown, trim):
    po = make_po(company, factory, vendor, owner, trim, "100", "100")
    line = po.lines.get()
    g = grns.create_grn(company=company, factory=factory, location=godown, vendor=vendor, date=DAY, user=owner, po=po,
                        lines=[grns.GrnLineSpec(item=trim, rate=D("100"), qty_received=D("60"), po_line=line)])
    grns.finish_qc(g, user=owner)
    grns.post_grn(g, user=owner)
    po.refresh_from_db()
    assert po.status == "partly_received" and orders.received_qty(line) == D("60.000")
    row = orders.pending_report(owner)[0]
    assert (row["ordered"], row["received"], row["pending"]) == (D("100.000"), D("60.000"), D("40.000"))
    with pytest.raises(BusinessRuleError, match="pending quantity"):
        grns.create_grn(company=company, factory=factory, location=godown, vendor=vendor, date=DAY, user=owner, po=po,
                        lines=[grns.GrnLineSpec(item=trim, rate=D("100"), qty_received=D("50"), po_line=line)])
    g2 = grns.create_grn(company=company, factory=factory, location=godown, vendor=vendor, date=DAY, user=owner, po=po,
                         lines=[grns.GrnLineSpec(item=trim, rate=D("100"), qty_received=D("40"), po_line=line)])
    grns.finish_qc(g2, user=owner)
    grns.post_grn(g2, user=owner)
    po.refresh_from_db()
    assert po.status == "received"


def test_short_close_needs_a_reason(company, factory, vendor, owner, trim):
    po = make_po(company, factory, vendor, owner, trim)
    with pytest.raises(BusinessRuleError):
        orders.short_close(po, user=owner, reason="")
    assert orders.short_close(po, user=owner, reason="Vendor cannot supply").status == "closed"


def test_po_needs_a_vendor_and_valid_lines(company, factory, owner, trim):
    cust = parties.create_party(company=company, name="Dealer", mobile="9822222222", is_customer=True)
    with pytest.raises(BusinessRuleError, match="not marked as a vendor"):
        orders.create_po(company=company, factory=factory, vendor=cust, date=DAY, user=owner,
                         lines=[orders.POLineSpec(trim, D("1"), D("1"))])


# ============================== GRN and QC (E5.2, E5.3) ==============================

def test_fabric_grn_receives_accepted_rolls_with_labels_and_books_grni(company, factory, vendor, owner, godown, fabric):
    g = fabric_grn(company, factory, vendor, godown, fabric, owner)
    line = g.lines.get()
    assert (line.qty_received, line.qty_accepted, line.qty_rejected) == (D("200.000"), D("180.000"), D("20.000"))
    assert g.number == "GRN/LDH1/26-27/0001" and g.status == "posted"
    rolls = FabricRoll.objects.filter(material=fabric)
    assert rolls.count() == 2 and all(r.label_code.startswith("R") and r.lot_no == "LOT-7" for r in rolls)  # rejected roll never enters stock
    assert stock.on_hand(factory, fabric) == (D("180.000"), D("36000.00"))
    assert bal(company, "stock_raw_material", factory) == D("36000.00") and bal(company, "grni", factory) == D("-36000.00")
    assert g.voucher.source_type == "purchases.grn"


def test_rejected_pieces_raise_a_draft_debit_note(company, factory, vendor, owner, godown, fabric):
    g = fabric_grn(company, factory, vendor, godown, fabric, owner)
    note = DebitNote.objects.get(grn=g)
    assert note.kind == "rejection" and note.status == "draft" and note.lines.get().qty == D("20.000")


def test_cannot_post_before_qc_and_every_roll_needs_a_decision(company, factory, vendor, owner, godown, fabric, trim):
    spec = grns.GrnLineSpec(item=fabric, rate=D("200"), rolls=[grns.RollSpec("A", D("10"))])
    g = grns.create_grn(company=company, factory=factory, location=godown, vendor=vendor, date=DAY, lines=[spec], user=owner)
    with pytest.raises(BusinessRuleError, match="Finish QC"):
        grns.post_grn(g, user=owner)
    with pytest.raises(BusinessRuleError, match="accepted or rejected"):
        grns.finish_qc(g, user=owner)


def test_accepted_with_remark_needs_a_remark(company, factory, vendor, owner, godown, trim):
    spec = grns.GrnLineSpec(item=trim, rate=D("10"), qty_received=D("100"), qty_rejected=D("5"))
    g = grns.create_grn(company=company, factory=factory, location=godown, vendor=vendor, date=DAY, lines=[spec], user=owner)
    with pytest.raises(BusinessRuleError, match="remark"):
        grns.finish_qc(g, user=owner)


def test_trim_grn_partial_rejection(company, factory, vendor, owner, godown, trim):
    g = trim_grn(company, factory, vendor, godown, trim, owner, "100", "10", "10", remark="10 bent")
    line = g.lines.get()
    assert (line.qty_accepted, line.qty_rejected, line.qc_status) == (D("90.000"), D("10.000"), "accepted_remark")
    assert stock.on_hand(factory, trim) == (D("90.000"), D("900.00"))


def test_duplicate_or_already_received_roll_numbers_are_refused(company, factory, vendor, owner, godown, fabric):
    fabric_grn(company, factory, vendor, godown, fabric, owner)
    spec = grns.GrnLineSpec(item=fabric, rate=D("200"), rolls=[grns.RollSpec("R1", D("10"))])
    with pytest.raises(BusinessRuleError, match="already received"):
        grns.create_grn(company=company, factory=factory, location=godown, vendor=vendor, date=DAY, lines=[spec], user=owner)
    twice = grns.GrnLineSpec(item=fabric, rate=D("200"), rolls=[grns.RollSpec("Z", D("10")), grns.RollSpec("Z", D("5"))])
    with pytest.raises(BusinessRuleError, match="twice"):
        grns.create_grn(company=company, factory=factory, location=godown, vendor=vendor, date=DAY, lines=[twice], user=owner)


def test_grn_needs_a_vendor_and_a_location_in_the_factory(company, factory, factory2, vendor, owner, trim):
    other = Location.objects.get(factory=factory2, name="Main Godown")
    with pytest.raises(BusinessRuleError, match="different factory"):
        grns.create_grn(company=company, factory=factory, location=other, vendor=vendor, date=DAY, user=owner,
                        lines=[grns.GrnLineSpec(item=trim, rate=D("1"), qty_received=D("1"))])


def test_store_keeper_cannot_receive_into_a_factory_they_lack(company, factory, factory2, vendor, trim):
    from core.models import Role

    keeper = make_user("keeper")
    keeper.roles.add(Role.objects.get(name="Store Keeper"))
    keeper.allowed_factories.add(factory)
    loc2 = Location.objects.get(factory=factory2, name="Main Godown")
    with pytest.raises(FactoryNotAllowed):
        grns.create_grn(company=company, factory=factory2, location=loc2, vendor=vendor, date=DAY, user=keeper,
                        lines=[grns.GrnLineSpec(item=trim, rate=D("1"), qty_received=D("1"))])


def test_cancelling_a_grn_reverses_stock_and_books_and_frees_the_roll_numbers(company, factory, vendor, owner, godown, fabric):
    g = fabric_grn(company, factory, vendor, godown, fabric, owner)
    grns.cancel_grn(g, user=owner, reason="Wrong vendor")
    assert stock.on_hand(factory, fabric) == (D("0.000"), D("0.00"))
    assert bal(company, "stock_raw_material", factory) == D("0.00") and bal(company, "grni", factory) == D("0.00")
    fabric_grn(company, factory, vendor, godown, fabric, owner)  # same roll numbers can be received again


@pytest.mark.raw_stock  # the issue stands in for cutting consumption, whose GL entry arrives with production
def test_cancelling_a_grn_is_refused_once_its_stock_is_used(company, factory, vendor, owner, godown, fabric):
    g = fabric_grn(company, factory, vendor, godown, fabric, owner)
    roll = FabricRoll.objects.filter(material=fabric).first()
    stock.post_movement(factory=factory, location=godown, item=fabric, qty=-roll.received_qty, roll=roll,
                        movement_type="issue", date=DAY, user=owner)
    with pytest.raises(BusinessRuleError):
        grns.cancel_grn(g, user=owner, reason="oops")
    g.refresh_from_db()
    assert g.status == "posted"


# ============================== purchase invoice (E5.4) ==============================

def test_invoice_without_tax_clears_grni_and_credits_the_vendor_bill_wise(company, factory, vendor, owner, godown, fabric):
    g = fabric_grn(company, factory, vendor, godown, fabric, owner)
    inv = bill(company, factory, vendor, owner, g.lines.get(), "180", "200")
    assert inv.number == "PI/LDH1/26-27/0001" and inv.payable == D("36000.00")
    assert bal(company, "grni", factory) == D("0.00")
    assert bal(company, "cgst_input", factory) == 0 and bal(company, "igst_input", factory) == 0  # nothing to tax ledgers
    assert outstanding_bills(vendor.payable_ledger)["bills"] == {"V-1": D("-36000.00")}


def test_gst_claimable_goes_to_input_ledgers(company, factory, vendor, owner, godown, fabric):
    g = fabric_grn(company, factory, vendor, godown, fabric, owner)
    inv = bill(company, factory, vendor, owner, g.lines.get(), "180", "200", tax_mode="template", gst_template=tpl(GST12))
    assert inv.gst_total == D("4320.00") and inv.payable == D("40320.00")
    assert bal(company, "cgst_input", factory) == D("2160.00") and bal(company, "sgst_input", factory) == D("2160.00")
    assert stock.on_hand(factory, fabric)[1] == D("36000.00")  # stock unchanged


def test_gst_not_claimable_is_added_to_item_cost(company, factory, vendor, owner, godown, fabric):
    g = fabric_grn(company, factory, vendor, godown, fabric, owner)
    inv = bill(company, factory, vendor, owner, g.lines.get(), "180", "200", tax_mode="template",
               gst_template=tpl(GST12), itc_claimable=False)
    assert inv.payable == D("40320.00")
    assert bal(company, "cgst_input", factory) == 0
    assert stock.on_hand(factory, fabric) == (D("180.000"), D("40320.00"))
    assert bal(company, "stock_raw_material", factory) == D("40320.00")


def test_reverse_charge_credits_rcm_payable_and_not_the_vendor(company, factory, vendor, owner, godown, fabric):
    g = fabric_grn(company, factory, vendor, godown, fabric, owner)
    inv = bill(company, factory, vendor, owner, g.lines.get(), "180", "200", tax_mode="reverse_charge",
               gst_template=tpl("GST 12% intra-state, reverse charge"))
    assert inv.payable == D("36000.00")
    assert bal(company, "cgst_rcm", factory) == D("-2160.00") and bal(company, "cgst_input", factory) == D("2160.00")


def test_manual_tax_lines_and_override_with_reason(company, factory, vendor, owner, godown, fabric):
    g = fabric_grn(company, factory, vendor, godown, fabric, owner)
    inv = bill(company, factory, vendor, owner, g.lines.get(), "90", "200", tax_mode="manual", manual_tax=[("igst", D("1800"))], no="M-1")
    assert inv.gst_total == D("1800.00") and bal(company, "igst_input", factory) == D("1800.00")
    with pytest.raises(BusinessRuleError, match="reason"):
        invoices.save_invoice(
            company=company, factory=factory, vendor=vendor, vendor_invoice_no="V-2", vendor_invoice_date=DAY, date=DAY,
            lines=[invoices.InvoiceLineSpec(g.lines.get(), D("90"), D("200"))], user=owner, tax_mode="template",
            gst_template=tpl(GST12), tax_overrides={"cgst": (D("1000"), "")})
    ok = invoices.save_invoice(
        company=company, factory=factory, vendor=vendor, vendor_invoice_no="V-3", vendor_invoice_date=DAY, date=DAY,
        lines=[invoices.InvoiceLineSpec(g.lines.get(), D("90"), D("200"))], user=owner, tax_mode="template",
        gst_template=tpl(GST12), tax_overrides={"cgst": (D("1000"), "Vendor charged round figure")})
    cg = ok.tax_lines.get(component="cgst")
    assert cg.amount == D("1000.00") and cg.is_override and "round" in cg.reason


def test_tds_is_deducted_only_when_selected(company, factory, vendor, owner, godown, fabric):
    g = fabric_grn(company, factory, vendor, godown, fabric, owner)
    inv = bill(company, factory, vendor, owner, g.lines.get(), "180", "200", tds_template=tpl("TDS 194C - others (2%)"))
    assert inv.tds_total == D("720.00") and inv.payable == D("35280.00")
    assert bal(company, "tds_payable", factory) == D("-720.00")
    assert outstanding_bills(vendor.payable_ledger)["bills"] == {"V-1": D("-35280.00")}


def test_rate_difference_is_capitalised_and_flagged_against_the_last_rate(company, factory, vendor, owner, godown, fabric):
    g1 = fabric_grn(company, factory, vendor, godown, fabric, owner)
    first = bill(company, factory, vendor, owner, g1.lines.get(), "180", "210", no="V-1")
    assert not first.lines.get().rate_variance  # no earlier purchase to compare with
    assert stock.on_hand(factory, fabric) == (D("180.000"), D("37800.00")) and bal(company, "grni", factory) == D("0.00")
    g2 = fabric_grn(company, factory, vendor, godown, fabric, owner, rolls=[("N1", "50", "accepted")])
    second = invoices.save_invoice(company=company, factory=factory, vendor=vendor, vendor_invoice_no="V-2",
                                   vendor_invoice_date=DAY, date=DAY, user=owner,
                                   lines=[invoices.InvoiceLineSpec(g2.lines.get(), D("50"), D("230"))])
    assert second.lines.get().rate_variance


def test_billing_more_than_is_left_or_a_foreign_grn_is_refused(company, factory, vendor, owner, godown, fabric):
    g = fabric_grn(company, factory, vendor, godown, fabric, owner)
    with pytest.raises(BusinessRuleError, match="left to bill"):
        bill(company, factory, vendor, owner, g.lines.get(), "201", "200")
    other = parties.create_party(company=company, name="Other Vendor", mobile="9844444444", is_vendor=True)
    with pytest.raises(BusinessRuleError, match="not a posted GRN"):
        bill(company, factory, other, owner, g.lines.get(), "10", "200")


def test_duplicate_vendor_invoice_numbers_are_refused(company, factory, vendor, owner, godown, fabric):
    g = fabric_grn(company, factory, vendor, godown, fabric, owner)
    bill(company, factory, vendor, owner, g.lines.get(), "10", "200", no="DUP")
    with pytest.raises(BusinessRuleError, match="already been entered"):
        bill(company, factory, vendor, owner, g.lines.get(), "10", "200", no="DUP")


def test_partial_billing_over_two_invoices_clears_grni_exactly(company, factory, vendor, owner, godown, fabric):
    g = fabric_grn(company, factory, vendor, godown, fabric, owner)
    line = g.lines.get()
    bill(company, factory, vendor, owner, line, "100", "200", no="P-1")
    assert bal(company, "grni", factory) == D("-16000.00")
    bill(company, factory, vendor, owner, line, "80", "200", no="P-2")
    assert bal(company, "grni", factory) == D("0.00")


def test_billing_rejected_pieces_parks_them_as_recoverable_until_the_debit_note(company, factory, vendor, owner, godown, fabric):
    g = fabric_grn(company, factory, vendor, godown, fabric, owner)
    note = DebitNote.objects.get(grn=g)
    with pytest.raises(BusinessRuleError, match="not billed"):
        debit_notes.post_debit_note(note, user=owner)  # nothing billed yet, nothing to recover
    inv = bill(company, factory, vendor, owner, g.lines.get(), "200", "200", tax_mode="template", gst_template=tpl(GST12))
    assert inv.payable == D("44800.00")
    assert bal(company, "grni", factory) == D("0.00")
    assert bal(company, "rejected_recoverable", factory) == D("4480.00")  # 4,000 + its 480 of GST
    assert bal(company, "cgst_input", factory) == D("2160.00")             # input credit only on the accepted part
    note = debit_notes.post_debit_note(note, user=owner)
    assert note.total == D("4480.00") and bal(company, "rejected_recoverable", factory) == D("0.00")
    # the vendor's debit, GST included, is set against the bill that billed the rejected rolls (E5.6)
    assert outstanding_bills(vendor.payable_ledger) == {"bills": {"V-1": D("-40320.00")}, "advance": D("0.00"), "on_account": D("0.00")}
    assert ledger_balance(vendor.payable_ledger) == D("-40320.00")
    with pytest.raises(BusinessRuleError, match="debit note has been posted"):
        invoices.cancel_invoice(inv, user=owner, reason="x")


def test_cancelling_an_invoice_restores_books_stock_and_billable_quantity(company, factory, vendor, owner, godown, fabric):
    g = fabric_grn(company, factory, vendor, godown, fabric, owner)
    inv = bill(company, factory, vendor, owner, g.lines.get(), "180", "210", tax_mode="template",
               gst_template=tpl(GST12), itc_claimable=False, tds_template=tpl("TDS 194C - others (2%)"))
    invoices.cancel_invoice(inv, user=owner, reason="Vendor sent a wrong bill")
    assert stock.on_hand(factory, fabric) == (D("180.000"), D("36000.00"))
    assert bal(company, "grni", factory) == D("-36000.00") and bal(company, "tds_payable", factory) == D("0.00")
    assert outstanding_bills(vendor.payable_ledger)["bills"] == {}
    assert invoices.billable_qty(g.lines.get()) == D("200.000")
    bill(company, factory, vendor, owner, g.lines.get(), "180", "200", no="V-1")  # the number can be reused after cancelling


def test_a_grn_cannot_be_cancelled_while_invoiced(company, factory, vendor, owner, godown, fabric):
    g = fabric_grn(company, factory, vendor, godown, fabric, owner)
    inv = bill(company, factory, vendor, owner, g.lines.get(), "180", "200")
    with pytest.raises(BusinessRuleError, match="invoiced"):
        grns.cancel_grn(g, user=owner, reason="x")
    invoices.cancel_invoice(inv, user=owner, reason="x")
    grns.cancel_grn(g, user=owner, reason="x")


def test_invoice_is_scoped_to_the_users_factory(company, factory, factory2, vendor, owner, accountant, godown, fabric):
    g = fabric_grn(company, factory, vendor, godown, fabric, owner)
    inv = invoices.save_invoice(company=company, factory=factory, vendor=vendor, vendor_invoice_no="S-1",
                                vendor_invoice_date=DAY, date=DAY, user=owner,
                                lines=[invoices.InvoiceLineSpec(g.lines.get(), D("10"), D("200"))])
    from purchases.models import PurchaseInvoice

    assert PurchaseInvoice.objects.for_user(accountant).count() == 1
    accountant.allowed_factories.set([factory2])
    assert PurchaseInvoice.objects.for_user(accountant).count() == 0
    with pytest.raises(FactoryNotAllowed):
        invoices.post_invoice(inv, user=accountant)


# ============================== return debit note (PUR-09) ==============================

def test_return_note_sends_stock_back_at_cost_and_balances_with_purchase_returns(company, factory, vendor, owner, godown, trim):
    trim_grn(company, factory, vendor, godown, trim, owner, "100", "0", "10")
    note = debit_notes.create_return_note(
        company=company, factory=factory, vendor=vendor, date=DAY, user=owner, reason="Wrong size",
        gst_template=tpl(GST12), lines=[debit_notes.ReturnLineSpec(trim, D("20"), D("12"), godown)])
    assert (note.subtotal, note.tax_total, note.total) == (D("240.00"), D("28.80"), D("268.80"))
    note = debit_notes.post_debit_note(note, user=owner)
    assert stock.on_hand(factory, trim) == (D("80.000"), D("800.00"))
    assert bal(company, "cgst_input", factory) == D("-14.40")
    assert bal(company, "purchase_returns", factory) == D("-40.00")  # 240 + tax 28.80 - 200 stock - 28.80 input
    assert note.number.startswith("DN/LDH1/")
    debit_notes.cancel_debit_note(note, user=owner, reason="Taken back")
    assert stock.on_hand(factory, trim) == (D("100.000"), D("1000.00")) and bal(company, "purchase_returns", factory) == D("0.00")


def test_return_note_for_fabric_needs_the_roll(company, factory, vendor, owner, godown, fabric):
    fabric_grn(company, factory, vendor, godown, fabric, owner)
    roll = FabricRoll.objects.filter(material=fabric).first()
    note = debit_notes.create_return_note(
        company=company, factory=factory, vendor=vendor, date=DAY, user=owner, reason="Shade mismatch",
        lines=[debit_notes.ReturnLineSpec(fabric, D("10"), D("200"), godown)])
    with pytest.raises(BusinessRuleError, match="by roll"):
        debit_notes.post_debit_note(note, user=owner)
    note2 = debit_notes.create_return_note(
        company=company, factory=factory, vendor=vendor, date=DAY, user=owner, reason="Shade mismatch",
        lines=[debit_notes.ReturnLineSpec(fabric, D("10"), D("200"), godown, roll=roll)])
    debit_notes.post_debit_note(note2, user=owner)
    assert stock.on_hand(factory, fabric)[0] == D("170.000")


# ============================== direct purchase invoice: bill and inward stock in one ==============================

def direct(company, factory, vendor, owner, godown, items, no="D-1", post=True, **kw):
    inv = invoices.save_invoice(
        company=company, factory=factory, vendor=vendor, vendor_invoice_no=no, vendor_invoice_date=DAY, date=DAY,
        lines=[invoices.InvoiceLineSpec(None, D(q), D(r), item=i) for i, q, r in items], user=owner, location=godown, **kw)
    return invoices.post_invoice(inv, user=owner) if post else inv


def test_a_direct_invoice_brings_the_goods_into_stock_and_books_the_purchase_with_no_grn(company, factory, vendor, owner, godown, trim):
    inv = direct(company, factory, vendor, owner, godown, [(trim, "100", "10")])
    assert inv.is_direct and inv.status == "posted" and inv.payable == D("1000.00") and not Grn.objects.exists()
    assert stock.on_hand(factory, trim) == (D("100.000"), D("1000.00"))
    assert StockMovement.objects.get(movement_type="receipt").location == godown
    assert bal(company, "stock_raw_material", factory) == D("1000.00") and bal(company, "grni", factory) == D("0.00")
    assert bal(company, "cgst_input", factory) == 0                                  # tax is optional
    assert outstanding_bills(vendor.payable_ledger)["bills"] == {"D-1": D("-1000.00")}


def test_a_direct_invoice_takes_fabric_in_as_one_roll_per_line_without_roll_entry(company, factory, vendor, owner, godown, fabric):
    direct(company, factory, vendor, owner, godown, [(fabric, "150", "200")])
    roll = FabricRoll.objects.get(material=fabric)
    assert roll.received_qty == D("150.000") and roll.supplier == vendor
    assert stock.on_hand(factory, fabric) == (D("150.000"), D("30000.00"))


def test_a_direct_invoice_with_non_claimable_gst_adds_it_to_stock_cost(company, factory, vendor, owner, godown, trim):
    inv = direct(company, factory, vendor, owner, godown, [(trim, "100", "10")], tax_mode="template",
                 gst_template=tpl(GST12), itc_claimable=False)
    assert inv.payable == D("1120.00") and stock.on_hand(factory, trim) == (D("100.000"), D("1120.00"))
    claim = direct(company, factory, vendor, owner, godown, [(trim, "100", "10")], no="D-2", tax_mode="template", gst_template=tpl(GST12))
    assert claim.payable == D("1120.00") and bal(company, "cgst_input", factory) == D("60.00")
    assert stock.on_hand(factory, trim)[1] == D("2120.00")


def test_a_direct_invoice_flags_a_changed_rate_and_cancelling_reverses_stock_and_books(company, factory, vendor, owner, godown, fabric, trim):
    direct(company, factory, vendor, owner, godown, [(trim, "100", "10")], no="D-1")
    second = direct(company, factory, vendor, owner, godown, [(trim, "50", "12"), (fabric, "10", "200")], no="D-2")
    assert second.lines.get(material=trim).rate_variance and not second.lines.get(material=fabric).rate_variance
    invoices.cancel_invoice(second, user=owner, reason="Wrong bill")
    assert stock.on_hand(factory, trim) == (D("100.000"), D("1000.00")) and stock.on_hand(factory, fabric)[0] == 0
    direct(company, factory, vendor, owner, godown, [(fabric, "10", "200")], no="D-2")   # can be entered again


def test_cancelling_a_direct_invoice_is_refused_once_the_goods_are_used(company, factory, vendor, owner, godown, trim):
    inv = direct(company, factory, vendor, owner, godown, [(trim, "100", "10")])
    back = debit_notes.create_return_note(
        company=company, factory=factory, vendor=vendor, date=DAY, user=owner, reason="Too many",
        lines=[debit_notes.ReturnLineSpec(trim, D("60"), D("10"), godown)])
    debit_notes.post_debit_note(back, user=owner)                                    # 60 of the 100 go back
    with pytest.raises(Exception, match="Only 40"):
        invoices.cancel_invoice(inv, user=owner, reason="Oops")


def test_direct_invoice_rules(company, factory, factory2, vendor, owner, godown, trim):
    with pytest.raises(BusinessRuleError, match="at least one item"):
        direct(company, factory, vendor, owner, godown, [])
    with pytest.raises(BusinessRuleError, match="more than zero"):
        direct(company, factory, vendor, owner, godown, [(trim, "0", "10")])
    with pytest.raises(BusinessRuleError, match="twice"):
        direct(company, factory, vendor, owner, godown, [(trim, "1", "10"), (trim, "2", "10")])
    other = Location.objects.get(factory=factory2, name="Main Godown")
    with pytest.raises(BusinessRuleError, match="different factory"):
        direct(company, factory, vendor, owner, other, [(trim, "1", "10")])
    inv = direct(company, factory, vendor, owner, godown, [(trim, "1", "10")], post=False)
    with pytest.raises(BusinessRuleError, match="cannot be changed"):
        invoices.save_invoice(company=company, factory=factory, vendor=vendor, vendor_invoice_no="D-1", vendor_invoice_date=DAY,
                              date=DAY, lines=[], user=owner, invoice=inv)


def test_the_invoice_screen_saves_and_posts_a_direct_purchase(company, factory, vendor, owner, godown, trim):
    from django.test import Client
    from django.urls import reverse

    c = Client()
    c.force_login(owner)
    html = c.get(reverse("invoice_new"), {"vendor": vendor.pk, "mode": "direct"}).content.decode()
    assert 'name="item"' in html and 'name="location"' in html and 'value="direct"' in html
    r = c.post(reverse("invoice_new"), {
        "vendor": vendor.pk, "mode": "direct", "location": godown.pk, "vendor_invoice_no": "D-9", "vendor_invoice_date": "2026-06-15",
        "date": "2026-06-15", "tax_mode": "none", "item": [f"m:{trim.pk}", ""], "qty": ["25", ""], "rate": ["8", ""]})
    from purchases.models import PurchaseInvoice

    inv = PurchaseInvoice.objects.get()
    assert r.status_code == 302 and inv.is_direct and inv.subtotal == D("200.00")
    c.post(reverse("invoice_detail", args=[inv.pk]), {"action": "post"})
    assert stock.on_hand(factory, trim) == (D("25.000"), D("200.00"))
    assert "Direct" in c.get(reverse("invoice_detail", args=[inv.pk])).content.decode()


# ============================== a rejection return is set against the supplier's bill (E5.6) ==============================

def rejected_and_billed(company, factory, vendor, godown, trim, owner, billed="100", no="V-1"):
    """100 zippers at 100 received, 20 rejected; the vendor billed `billed` of them. Returns (grn, draft note, bill)."""
    g = trim_grn(company, factory, vendor, godown, trim, owner, qty="100", rejected="20", rate="100", remark="broken")
    return g, DebitNote.objects.get(grn=g), bill(company, factory, vendor, owner, g.lines.get(), billed, "100", no=no)


def pay_bill(company, factory, vendor, owner, amount, ref="V-1"):
    from ledger.models import Ledger
    from ledger.services.manual import Row, post_manual_voucher

    cash = Ledger.objects.get(company=company, system_key="cash")
    return post_manual_voucher(
        company=company, factory=factory, vtype="payment", on_date=DAY, narration="", header={"account": str(cash.pk)},
        rows=[Row(ledger=str(vendor.payable_ledger_id), amount=amount, ref_type="against", reference=ref)], user=owner)


def position(vendor):
    got = outstanding_bills(vendor.payable_ledger)
    return got["bills"], got["on_account"], ledger_balance(vendor.payable_ledger)


def test_a_rejection_return_reduces_the_bill_it_relates_to_and_the_rest_is_paid_off(company, factory, vendor, owner, godown, trim):
    g, note, inv = rejected_and_billed(company, factory, vendor, godown, trim, owner)
    assert position(vendor) == ({"V-1": D("-10000.00")}, D("0.00"), D("-10000.00"))
    note = debit_notes.post_debit_note(note, user=owner)
    assert note.total == D("2000.00")
    # the bill shows 8,000 unpaid, the supplier is owed 8,000 and nothing sits on account
    assert position(vendor) == ({"V-1": D("-8000.00")}, D("0.00"), D("-8000.00"))
    # only the bill-wise allocation of the supplier line is new: the voucher's ledgers and amounts are as before
    lines = {l.ledger.system_key or "vendor": (l.debit, l.credit) for l in note.voucher.lines.select_related("ledger")}
    assert lines == {"vendor": (D("2000.00"), D("0.00")), "rejected_recoverable": (D("0.00"), D("2000.00"))}
    allocs = [(a.ref_type, a.reference, a.amount, a.due_date) for l in note.voucher.lines.all() for a in l.allocations.all()]
    assert allocs == [("against", "V-1", D("2000.00"), DAY + timedelta(days=30))]      # the bill's own reference and due date
    assert bal(company, "rejected_recoverable", factory) == D("0.00") and note.voucher.voucher_type == "debit_note"
    assert not StockMovement.objects.filter(source_type=note._meta.label_lower).exists()
    pay_bill(company, factory, vendor, owner, "8000")
    assert position(vendor) == ({}, D("0.00"), D("0.00"))
    # the bill is settled: no further payment is taken against it
    with pytest.raises(BusinessRuleError, match="fully settled"):
        pay_bill(company, factory, vendor, owner, "1")


def test_cancelling_the_return_puts_the_bill_back(company, factory, vendor, owner, godown, trim):
    g, note, inv = rejected_and_billed(company, factory, vendor, godown, trim, owner)
    note = debit_notes.post_debit_note(note, user=owner)
    assert position(vendor)[0] == {"V-1": D("-8000.00")}
    debit_notes.cancel_debit_note(note, user=owner, reason="posted by mistake")
    assert position(vendor) == ({"V-1": D("-10000.00")}, D("0.00"), D("-10000.00"))
    assert bal(company, "rejected_recoverable", factory) == D("2000.00")
    # the whole bill can be paid again
    pay_bill(company, factory, vendor, owner, "10000")
    assert position(vendor) == ({}, D("0.00"), D("0.00"))


def test_what_the_bill_no_longer_has_open_stays_on_account(company, factory, vendor, owner, godown, trim):
    g, note, inv = rejected_and_billed(company, factory, vendor, godown, trim, owner)
    pay_bill(company, factory, vendor, owner, "9000")                       # only 1,000 is still open on the bill
    note = debit_notes.post_debit_note(note, user=owner)
    allocs = sorted((a.ref_type, a.reference, a.amount) for l in note.voucher.lines.all() for a in l.allocations.all())
    assert allocs == [("against", "V-1", D("1000.00")), ("on_account", "", D("1000.00"))]
    assert position(vendor) == ({}, D("1000.00"), D("1000.00"))             # the supplier owes us 1,000
    # a bill already paid in full: everything stays on account, exactly as before
    g2, note2, inv2 = rejected_and_billed(company, factory, vendor, godown, trim, owner, no="V-2")
    pay_bill(company, factory, vendor, owner, "10000", ref="V-2")
    note2 = debit_notes.post_debit_note(note2, user=owner)
    assert [(a.ref_type, a.amount) for l in note2.voucher.lines.all() for a in l.allocations.all()] == [("on_account", D("2000.00"))]
    assert position(vendor) == ({}, D("3000.00"), D("3000.00"))


def test_a_return_spanning_two_bills_is_set_against_each_for_its_own_share(company, factory, vendor, owner, godown, trim):
    g = trim_grn(company, factory, vendor, godown, trim, owner, qty="100", rejected="20", rate="100", remark="broken")
    line = g.lines.get()
    bill(company, factory, vendor, owner, line, "85", "100", no="V-1")      # 80 accepted and 5 of the rejected
    bill(company, factory, vendor, owner, line, "15", "100", no="V-2")      # the other 15 rejected
    note = debit_notes.post_debit_note(DebitNote.objects.get(grn=g), user=owner)
    allocs = [(a.ref_type, a.reference, a.amount) for l in note.voucher.lines.all() for a in l.allocations.order_by("id")]
    assert allocs == [("against", "V-1", D("500.00")), ("against", "V-2", D("1500.00"))] and note.total == D("2000.00")
    assert position(vendor) == ({"V-1": D("-8000.00")}, D("0.00"), D("-8000.00"))   # V-2 billed only rejected goods: nothing left on it


def test_a_second_return_takes_only_the_bill_that_made_it_postable(company, factory, vendor, owner, godown, trim):
    g = trim_grn(company, factory, vendor, godown, trim, owner, qty="100", rejected="20", rate="100", remark="broken")
    line = g.lines.get()
    bill(company, factory, vendor, owner, line, "85", "100", no="V-1")
    first = debit_notes.post_debit_note(DebitNote.objects.get(grn=g), user=owner)          # 500 against V-1
    assert first.total == D("500.00") and position(vendor)[0] == {"V-1": D("-8000.00")}
    bill(company, factory, vendor, owner, line, "15", "100", no="V-2")
    second = DebitNote.objects.create(company=company, factory=factory, kind="rejection", vendor=vendor, grn=g, date=DAY,
                                      reason="Rest of the rejected zippers", created_by=owner)
    second.lines.create(grn_line=line, qty=D("15"), rate=D("100"), amount=D("0"), material=trim)
    second = debit_notes.post_debit_note(second, user=owner)
    allocs = [(a.ref_type, a.reference, a.amount) for l in second.voucher.lines.all() for a in l.allocations.all()]
    assert allocs == [("against", "V-2", D("1500.00"))]
    assert position(vendor) == ({"V-1": D("-8000.00")}, D("0.00"), D("-8000.00"))


def test_a_return_of_goods_in_stock_still_goes_on_account(company, factory, vendor, owner, godown, trim):
    g = trim_grn(company, factory, vendor, godown, trim, owner)
    bill(company, factory, vendor, owner, g.lines.get(), "100", "10")
    note = debit_notes.create_return_note(
        company=company, factory=factory, vendor=vendor, date=DAY, user=owner, reason="Wrong size", grn=g,
        lines=[debit_notes.ReturnLineSpec(trim, D("20"), D("10"), godown)])
    note = debit_notes.post_debit_note(note, user=owner)
    assert [(a.ref_type, a.amount) for l in note.voucher.lines.all() for a in l.allocations.all()] == [("on_account", D("200.00"))]
    assert position(vendor) == ({"V-1": D("-1000.00")}, D("200.00"), D("-800.00"))


def test_whom_i_owe_shows_the_bill_less_the_return(company, factory, vendor, owner, godown, trim):
    from reports.services.books import ageing

    g, note, inv = rejected_and_billed(company, factory, vendor, godown, trim, owner)
    debit_notes.post_debit_note(note, user=owner)
    report = ageing(company, user=owner, kind="creditors", as_of=DAY)
    party = next(p for p in report["parties"] if p["ledger"] == vendor.payable_ledger)
    assert party["total"] == D("8000.00") and party["unadjusted"] == D("0.00") and report["total"] == D("8000.00")
    assert [(b["reference"], b["amount"], b["due"]) for b in party["bills"]] == [("V-1", D("8000.00"), DAY + timedelta(days=30))]
