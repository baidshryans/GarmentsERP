"""Sales services (E4.1 - E4.7): pricing, orders, MTO, packing, invoices with optional GST, credit notes, e-invoice.
The autouse fixture in conftest then checks the books tally and stock (with finished-goods value) reconciles."""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from core.exceptions import BusinessRuleError, FactoryNotAllowed
from core.models import Location, Role
from inventory.models import StockBalance
from ledger.models import Ledger
from ledger.selectors import ledger_balance, outstanding_bills
from production.models import ProductionOrder
from sales.models import SaleInvoice, SaleOrder
from sales.services import credit_notes, einvoice, invoices, orders, packing, pricing
from sales.services.einvoice import EInvoiceError
from sales.services.invoices import InvoiceLineSpec
from sales.services.orders import OrderLineSpec
from tax.models import TaxTemplate
from tests import sales_helpers as h
from tests.conftest import make_user

D = h.D
DAY = h.DAY


@pytest.fixture
def ns(company, factory, owner):
    return h.build(company, factory, owner)


def bal(company, key, factory=None):
    return ledger_balance(Ledger.objects.get(company=company, system_key=key), factory=factory)


def stock_at(ns, sku):
    return StockBalance.objects.get(location=ns.godown, sku=sku).qty


def quick_invoice(ns, customer=None, qty="10", rate="500", color="Black", size="M", date_=DAY, post=True, **kw):
    customer = customer or ns.local
    inv = invoices.save_invoice(
        company=ns.company, factory=ns.factory, customer=customer, date=date_, user=ns.owner, location=ns.godown,
        lines=[InvoiceLineSpec(ns.sku(color, size), D(qty), D(rate), D("0"))], **kw)
    return invoices.post_invoice(inv, user=ns.owner) if post else inv


# ---------------------------------------------------------------- E4.3 rate lookup, A6

def test_rate_comes_from_customer_rate_then_price_list_slab_then_last_rate(ns):
    sku = ns.sku("Black", "M")
    assert pricing.resolve(ns.local, sku, 10, DAY) is None
    ns.local.price_list = h.price_list(ns, "450")
    h.price_list(ns, "420", min_qty=100)
    ns.local.save()
    p = pricing.resolve(ns.local, sku, 10, DAY)
    assert (p.rate, p.source) == (D("450.00"), "price list")
    assert pricing.resolve(ns.local, sku, 150, DAY).rate == D("420.00")             # the quantity slab
    h.customer_rate(ns, ns.local, "400")
    p = pricing.resolve(ns.local, sku, 150, DAY)
    assert (p.rate, p.source) == (D("400.00"), "customer rate")                     # the customer's own rate wins
    ns.local.price_list = None
    ns.local.save()
    h.CustomerRate.objects.all().delete()
    quick_invoice(ns, rate="475")
    p = pricing.resolve(ns.local, sku, 5, DAY)
    assert (p.rate, p.source) == (D("475.00"), "last rate")


def test_a_new_price_does_not_change_old_orders_A6(ns, factory, owner):
    pl = h.price_list(ns, "450")
    ns.local.price_list, ns.local.discount_pct = pl, D("5")
    ns.local.save()
    old = orders.create_order(company=ns.company, factory=factory, customer=ns.local, date=DAY, user=owner,
                              lines=[OrderLineSpec(ns.sku("Black", "M"), D("20"))])
    line = old.lines.get()
    assert (line.rate, line.discount_pct, line.amount) == (D("450.00"), D("5.00"), D("8550.00"))
    h.price_list(ns, "500", effective=date(2026, 6, 20))                              # a later rate arrives
    assert pricing.resolve(ns.local, ns.sku("Black", "M"), 20, date(2026, 6, 25)).rate == D("500.00")
    line.refresh_from_db()
    assert line.rate == D("450.00")                                                   # the old order is untouched
    assert pricing.resolve(ns.local, ns.sku("Black", "M"), 20, DAY).rate == D("450.00")


def test_discount_above_the_limit_needs_the_permission(ns, factory, owner, accountant):
    with pytest.raises(BusinessRuleError, match="above your limit"):
        orders.create_order(company=ns.company, factory=factory, customer=ns.local, date=DAY, user=accountant,
                            lines=[OrderLineSpec(ns.sku("Black", "M"), D("5"), D("500"), D("12"))])
    o = orders.create_order(company=ns.company, factory=factory, customer=ns.local, date=DAY, user=owner,
                            lines=[OrderLineSpec(ns.sku("Black", "M"), D("5"), D("500"), D("12"))])    # the owner may
    assert o.lines.get().discount_pct == D("12.00")


# ---------------------------------------------------------------- orders and MTO (E4.1, E4.7, A5)

def test_order_numbers_whole_pieces_and_float_refusal(ns, factory, owner):
    o = orders.create_order(company=ns.company, factory=factory, customer=ns.local, date=DAY, user=owner, remarks="r",
                            lines=[OrderLineSpec(ns.sku("Black", s), D("10"), D("500")) for s in "SM"] +
                                  [OrderLineSpec(ns.sku("Navy", "L"), D("4"), D("500"))])
    assert o.status == "draft" and o.number is None and o.total_qty == D("24")
    o = orders.confirm_order(o, user=owner)
    assert o.status == "confirmed" and o.number.startswith("SO/LDH1/")
    for bad in (D("2.5"), 3.0, D("0")):
        with pytest.raises(BusinessRuleError):
            orders.create_order(company=ns.company, factory=factory, customer=ns.local, date=DAY, user=owner,
                                lines=[OrderLineSpec(ns.sku("Black", "M"), bad, D("500"))])
    with pytest.raises(BusinessRuleError, match="not marked as a customer"):
        vendor = h.parties.create_party(company=ns.company, name="V", mobile="9833333300", is_vendor=True)
        orders.create_order(company=ns.company, factory=factory, customer=vendor, date=DAY, user=owner,
                            lines=[OrderLineSpec(ns.sku("Black", "M"), D("1"), D("500"))])


def test_an_mto_order_raises_a_production_requirement_that_never_shows_the_customer_A5(ns, factory, owner):
    from masters.services.parties import update_party

    o = orders.create_order(company=ns.company, factory=factory, customer=ns.far, date=DAY, user=owner, order_type="mto",
                            due_date=date(2026, 7, 10), lines=[OrderLineSpec(ns.sku("Navy", s), D(q), D("520"))
                                                              for s, q in (("S", "10"), ("M", "20"), ("L", "20"), ("XL", "10"))])
    o = orders.confirm_order(o, user=owner)
    po = o.production_order
    assert po.purpose == "mto" and po.order_reference == o.number and po.status == "draft" and po.due_date == date(2026, 7, 10)
    line = po.lines.get()
    assert (line.style, line.colour.name, line.total_qty) == (ns.style, "Navy", 60)
    assert {s.size.code: s.qty for s in line.sizes.all()} == {"S": 10, "M": 20, "L": 20, "XL": 10}
    # nothing on the production side carries the customer: only the sale order number
    blob = " ".join(str(v) for v in (po.order_reference, po.remarks, po.number))
    assert ns.far.name not in blob and ns.far.mobile not in blob
    assert not any(f.name in ("customer", "party") for f in ProductionOrder._meta.get_fields())
    # a draft can be cancelled, which stops the requirement; once production is released the order cannot be
    orders.cancel_order(o, user=owner, reason="customer changed mind")
    assert SaleOrder.objects.get(pk=o.pk).status == "cancelled"


def test_cancel_refused_once_production_is_released(ns, factory, owner):
    from production.services import orders as prod_orders

    o = orders.create_order(company=ns.company, factory=factory, customer=ns.local, date=DAY, user=owner, order_type="mto",
                            lines=[OrderLineSpec(ns.sku("Navy", "M"), D("10"), D("520"))])
    o = orders.confirm_order(o, user=owner)
    ProductionOrder.objects.filter(pk=o.production_order_id).update(status="released")
    with pytest.raises(BusinessRuleError, match="released"):
        orders.cancel_order(o, user=owner, reason="x")


# ---------------------------------------------------------------- invoices without GST (E4.4: not registered), stock and books

def test_invoice_without_gst_posts_sales_stock_and_cost_in_one_go(ns, company, factory, owner):
    inv = quick_invoice(ns, qty="10", rate="500")
    assert inv.number.startswith("INV/LDH1/") and inv.status == "posted"
    assert (inv.subtotal, inv.gst_total, inv.total, inv.cogs_total) == (D("5000.00"), D("0.00"), D("5000.00"), D("3000.00"))
    assert inv.tax_mode == "none" and not inv.tax_lines.exists()
    assert stock_at(ns, ns.sku("Black", "M")) == D("90")
    assert bal(company, "sales_stock", factory) == D("-5000.00")
    assert bal(company, "cogs", factory) == D("3000.00")
    assert ledger_balance(ns.local.customer_ledger) == D("5000.00")
    for k in ("cgst_output", "sgst_output", "igst_output"):
        assert bal(company, k) == 0                                                      # nothing to a tax ledger
    assert outstanding_bills(ns.local.customer_ledger)["bills"] == {inv.number: D("5000.00")}
    assert inv.due_date == DAY + timedelta(days=30)
    with pytest.raises(BusinessRuleError, match="GST is not switched on"):
        quick_invoice(ns, tax_mode="template", gst_template=TaxTemplate.objects.get(name="GST 5% intra-state (CGST + SGST)"))


def test_not_enough_stock_saves_nothing(ns, company, factory, owner):
    before = SaleInvoice.objects.count()
    inv = quick_invoice(ns, qty="101", post=False)
    with pytest.raises(BusinessRuleError, match="Only 100"):
        invoices.post_invoice(inv, user=owner)
    inv.refresh_from_db()
    assert inv.status == "draft" and inv.number is None and inv.voucher is None
    assert stock_at(ns, ns.sku("Black", "M")) == D("100") and bal(company, "sales_stock") == 0


def test_the_total_rounds_to_the_rupee_into_round_off(ns, company, factory):
    inv = quick_invoice(ns, qty="3", rate="333.33")                                      # 999.99
    assert inv.total == D("1000.00") and inv.round_off == D("0.01")
    assert bal(company, "round_off", factory) == D("-0.01")
    from sales.services.common import settings_for

    s = settings_for(company)
    s.rounding = "none"
    s.save()
    inv = quick_invoice(ns, qty="3", rate="333.33")
    assert inv.total == D("999.99") and inv.round_off == 0


def test_money_must_be_decimal(ns, factory, owner):
    with pytest.raises(BusinessRuleError, match="Decimal"):
        invoices.save_invoice(company=ns.company, factory=factory, customer=ns.local, date=DAY, user=owner, location=ns.godown,
                              lines=[InvoiceLineSpec(ns.sku("Black", "M"), D("1"), 500.0, D("0"))])


# ---------------------------------------------------------------- GST on invoices (E4.4, A4)

def test_gst_is_suggested_from_the_slab_and_the_place_of_supply_A4(ns, company, factory):
    h.gst_on(company)
    local = quick_invoice(ns, ns.local, qty="10", rate="500")                           # 500 a piece: 5%, same state
    assert local.tax_mode == "auto" and local.gst_total == D("250.00") and local.total == D("5250.00")
    assert {(t.component, t.rate, t.amount) for t in local.tax_lines.all()} == {
        ("cgst", D("2.5"), D("125.00")), ("sgst", D("2.5"), D("125.00"))}
    assert bal(company, "cgst_output", factory) == D("-125.00") and bal(company, "sgst_output", factory) == D("-125.00")
    assert bal(company, "igst_output", factory) == 0
    far = quick_invoice(ns, ns.far, qty="10", rate="500")                                # Maharashtra: IGST
    assert [(t.component, t.amount) for t in far.tax_lines.all()] == [("igst", D("250.00"))]
    assert far.place_of_supply == "27" and bal(company, "igst_output", factory) == D("-250.00")


def test_a_dearer_piece_falls_in_the_18_percent_slab_and_mixed_lines_are_taxed_each_at_its_own_rate(ns, company):
    h.gst_on(company)
    inv = invoices.save_invoice(
        company=company, factory=ns.factory, customer=ns.local, date=DAY, user=ns.owner, location=ns.godown,
        lines=[InvoiceLineSpec(ns.sku("Black", "S"), D("2"), D("2500.00"), D("0")),
               InvoiceLineSpec(ns.sku("Black", "M"), D("2"), D("2600.00"), D("0"))])
    rates = {l.sku.size.code: l.gst_rate for l in inv.lines.all()}
    assert rates == {"S": D("5.00"), "M": D("18.00")}
    assert inv.gst_total == D("250.00") + D("936.00")
    inv = invoices.post_invoice(inv, user=ns.owner)
    assert inv.total == D("10200.00") + D("1186.00") and {t.rate for t in inv.tax_lines.all()} == {D("2.5"), D("9")}


def test_gst_can_be_waived_on_one_invoice_with_a_reason_that_is_logged(ns, company, factory):
    h.gst_on(company)
    with pytest.raises(BusinessRuleError, match="reason"):
        quick_invoice(ns, tax_mode="none")
    inv = quick_invoice(ns, tax_mode="none", tax_note="Export under LUT")
    assert inv.tax_mode == "none" and inv.gst_total == 0 and inv.total == D("5000.00") and not inv.tax_lines.exists()
    assert inv.tax_note == "Export under LUT" and "GST 5% intra-state" in inv.suggested_tax     # what was suggested is kept
    assert bal(company, "cgst_output") == 0 and bal(company, "igst_output") == 0
    nxt = quick_invoice(ns)                                                              # the next invoice is taxed again
    assert nxt.tax_mode == "auto" and nxt.gst_total == D("250.00")


def test_changing_the_template_needs_a_note_and_one_template_covers_the_invoice(ns, company):
    h.gst_on(company)
    t12 = TaxTemplate.objects.get(name="GST 12% intra-state (CGST + SGST)")
    with pytest.raises(BusinessRuleError, match="reason"):
        quick_invoice(ns, tax_mode="template", gst_template=t12)
    inv = quick_invoice(ns, tax_mode="template", gst_template=t12, tax_note="Accountant: classified under 12%")
    assert inv.gst_total == D("600.00") and inv.gst_template == t12
    same = TaxTemplate.objects.get(name="GST 5% intra-state (CGST + SGST)")
    inv2 = quick_invoice(ns, tax_mode="template", gst_template=same)                    # same as suggested: no note needed
    assert inv2.gst_total == D("250.00")
    with pytest.raises(BusinessRuleError, match="reverse charge"):
        quick_invoice(ns, tax_mode="template", gst_template=TaxTemplate.objects.get(name="GST 5% intra-state, reverse charge"),
                      tax_note="x")


def test_a_style_without_hsn_or_slab_stops_auto_gst_but_can_still_be_billed_with_a_choice(ns, company):
    h.gst_on(company)
    ns.style.hsn = None
    ns.style.save()
    with pytest.raises(BusinessRuleError, match="no HSN"):
        quick_invoice(ns)
    inv = quick_invoice(ns, tax_mode="none", tax_note="HSN to be fixed")
    assert inv.status == "posted"


def test_gst_switched_on_from_a_date_only_taxes_invoices_from_that_date(ns, company):
    from tax import services as ts

    ts.set_tax_status(company=company, kind="gst", enabled=True, effective_from=date(2026, 6, 1), registration_number=h.GSTIN)
    before = quick_invoice(ns, date_=date(2026, 5, 20))
    after = quick_invoice(ns, date_=date(2026, 6, 20))
    assert before.gst_total == 0 and after.gst_total == D("250.00")


# ---------------------------------------------------------------- packing and partial dispatch (E4.6, A7)

def confirmed_order(ns, qty="30", rate="500"):
    o = orders.create_order(company=ns.company, factory=ns.factory, customer=ns.local, date=DAY, user=ns.owner,
                            lines=[OrderLineSpec(ns.sku("Black", s), D(qty), D(rate), D("0")) for s in ("S", "M")])
    return orders.confirm_order(o, user=ns.owner)


def pack(ns, order, cartons):
    specs = [packing.CartonSpec({ns.sku("Black", s): D(q) for s, q in c.items()}) for c in cartons]
    p = packing.save_packing(order=order, location=ns.godown, date=DAY, cartons=specs, user=ns.owner, lr_no="LR-77",
                             transporter=None, vehicle_no="pb10ab1234")
    return packing.finalize_packing(p, user=ns.owner)


def test_partial_dispatch_packing_by_carton_invoice_for_packed_pieces_and_balance_pending_A7(ns, company, factory):
    order = confirmed_order(ns)                                                          # 30 S + 30 M
    p = pack(ns, order, [{"S": "10", "M": "5"}, {"S": "5", "M": "10"}])
    assert p.number.startswith("PKL/LDH1/") and p.total_qty == D("30") and p.vehicle_no == "PB10AB1234"
    assert [c.code for c in p.cartons.all()] == [f"C{p.pk:06d}-01", f"C{p.pk:06d}-02"]
    assert {l.sku.size.code: l.qty_packed for l in order.lines.all()} == {"S": D("15"), "M": D("15")}
    inv = invoices.invoice_from_packing(p, user=ns.owner, date=DAY)
    assert {l.sku.size.code: l.qty for l in inv.lines.all()} == {"S": D("15"), "M": D("15")}   # only what was packed
    inv = invoices.post_invoice(inv, user=ns.owner)
    order.refresh_from_db()
    assert order.status == "partly_dispatched" and order.balance_qty == D("30")             # balance pending
    assert stock_at(ns, ns.sku("Black", "S")) == D("85")
    assert [r["balance"] for r in orders.order_book(ns.owner)] == [D("30")]
    p.refresh_from_db()
    assert p.status == "invoiced" and inv.lr_no == "LR-77"
    # second dispatch for the rest completes the order
    p2 = pack(ns, order, [{"S": "15", "M": "15"}])
    invoices.post_invoice(invoices.invoice_from_packing(p2, user=ns.owner, date=DAY), user=ns.owner)
    order.refresh_from_db()
    assert order.status == "dispatched" and order.balance_qty == 0 and orders.order_book(ns.owner) == []


def test_packing_more_than_ordered_or_in_stock_is_refused(ns):
    order = confirmed_order(ns, qty="30")
    with pytest.raises(BusinessRuleError, match="left to pack"):
        pack(ns, order, [{"S": "31"}])
    pack(ns, order, [{"S": "20"}])
    with pytest.raises(BusinessRuleError, match="left to pack"):
        pack(ns, order, [{"S": "11"}])                                                   # 20 already packed on another list
    order2 = orders.confirm_order(orders.create_order(
        company=ns.company, factory=ns.factory, customer=ns.local, date=DAY, user=ns.owner,
        lines=[OrderLineSpec(ns.sku("Navy", "S"), D("150"), D("500"), D("0"))]), user=ns.owner)
    p = packing.save_packing(order=order2, location=ns.godown, date=DAY, user=ns.owner,
                             cartons=[packing.CartonSpec({ns.sku("Navy", "S"): D("150")})])
    with pytest.raises(BusinessRuleError, match="available"):
        packing.finalize_packing(p, user=ns.owner)


def test_the_invoice_cannot_cover_more_than_was_packed_and_a_cancelled_list_frees_the_order(ns):
    order = confirmed_order(ns)
    p = pack(ns, order, [{"S": "10"}])
    with pytest.raises(BusinessRuleError, match="only packed pieces"):
        invoices.save_invoice(company=ns.company, factory=ns.factory, customer=ns.local, date=DAY, user=ns.owner,
                              location=ns.godown, order=order, packing=p,
                              lines=[InvoiceLineSpec(ns.sku("Black", "S"), D("11"), D("500"), D("0"))])
    packing.cancel_packing(p, user=ns.owner, reason="wrong goods")
    assert all(l.qty_packed == 0 for l in order.lines.all())
    pack(ns, order, [{"S": "30"}])


def test_an_invoice_against_an_order_cannot_exceed_the_order(ns):
    order = confirmed_order(ns, qty="10")
    with pytest.raises(BusinessRuleError, match="left to invoice"):
        invoices.save_invoice(company=ns.company, factory=ns.factory, customer=ns.local, date=DAY, user=ns.owner,
                              location=ns.godown, order=order,
                              lines=[InvoiceLineSpec(ns.sku("Black", "S"), D("11"), D("500"), D("0"))])


def test_cancelling_the_invoice_returns_stock_reverses_the_books_and_reopens_the_order(ns, company, factory):
    order = confirmed_order(ns)
    p = pack(ns, order, [{"S": "10", "M": "10"}])
    inv = invoices.post_invoice(invoices.invoice_from_packing(p, user=ns.owner, date=DAY), user=ns.owner)
    with pytest.raises(BusinessRuleError, match="reason"):
        invoices.cancel_invoice(inv, user=ns.owner, reason=" ")
    invoices.cancel_invoice(inv, user=ns.owner, reason="wrong customer")
    assert stock_at(ns, ns.sku("Black", "S")) == D("100")
    assert bal(company, "sales_stock") == 0 and bal(company, "cogs") == 0 and ledger_balance(ns.local.customer_ledger) == 0
    order.refresh_from_db()
    p.refresh_from_db()
    assert order.status == "confirmed" and all(l.qty_invoiced == 0 for l in order.lines.all()) and p.status == "packed"
    invoices.post_invoice(invoices.invoice_from_packing(p, user=ns.owner, date=DAY), user=ns.owner)   # can be invoiced again


# ---------------------------------------------------------------- credit notes (A8)

def test_credit_note_reverses_gst_restores_stock_at_cost_and_reduces_the_outstanding_A8(ns, company, factory):
    h.gst_on(company)
    inv = quick_invoice(ns, qty="10", rate="500")                                        # 5000 + 250 GST = 5250
    note = credit_notes.save_credit_note(invoice=inv, location=ns.godown, date=DAY + timedelta(days=3), user=ns.owner,
                                         lines=[(inv.lines.get(), D("4"))], reason="Wrong colour")
    assert (note.subtotal, note.gst_total, note.total) == (D("2000.00"), D("100.00"), D("2100.00"))
    note = credit_notes.post_credit_note(note, user=ns.owner)
    assert note.number.startswith("SCN/LDH1/") and note.status == "posted"
    assert stock_at(ns, ns.sku("Black", "M")) == D("94")
    assert bal(company, "sales_returns", factory) == D("2000.00") and bal(company, "cogs", factory) == D("1800.00")
    assert bal(company, "cgst_output", factory) == D("-75.00") and bal(company, "sgst_output", factory) == D("-75.00")
    assert outstanding_bills(ns.local.customer_ledger)["bills"] == {inv.number: D("3150.00")}   # outstanding falls
    line = inv.lines.get()
    assert line.qty_returned == D("4") and line.returnable == D("6")
    # the rest: exact remainders, nothing left over or lost
    note2 = credit_notes.post_credit_note(credit_notes.save_credit_note(
        invoice=inv, location=ns.godown, date=DAY + timedelta(days=4), user=ns.owner, lines=[(line, D("6"))],
        reason="Rest"), user=ns.owner)
    assert (note2.subtotal, note2.gst_total, note2.total) == (D("3000.00"), D("150.00"), D("3150.00"))
    assert outstanding_bills(ns.local.customer_ledger)["bills"] == {} and ledger_balance(ns.local.customer_ledger) == 0
    assert bal(company, "cgst_output") == 0 and bal(company, "cogs") == 0 and bal(company, "sales_returns") == D("5000.00")
    with pytest.raises(BusinessRuleError, match="only 0"):
        credit_notes.save_credit_note(invoice=inv, location=ns.godown, date=DAY + timedelta(days=5), user=ns.owner,
                                      lines=[(line, D("1"))], reason="Again")


def test_credit_note_after_payment_leaves_the_credit_on_account(ns, company, factory, owner):
    from ledger.services.posting import AllocationSpec, LineSpec, post_voucher

    inv = quick_invoice(ns, qty="10", rate="500")
    post_voucher(company=company, factory=factory, voucher_type="receipt", date=DAY, user=owner, lines=[
        LineSpec(ledger=Ledger.objects.get(company=company, system_key="cash"), debit=D("5000.00")),
        LineSpec(ledger=ns.local.customer_ledger, credit=D("5000.00"),
                 allocations=(AllocationSpec("against", D("5000.00"), inv.number),))])
    note = credit_notes.post_credit_note(credit_notes.save_credit_note(
        invoice=inv, location=ns.godown, date=DAY, user=owner, lines=[(inv.lines.get(), D("2"))], reason="Damaged"), user=owner)
    assert note.total == D("1000.00")
    assert outstanding_bills(ns.local.customer_ledger)["on_account"] == D("-1000.00")        # we owe the customer 1000


def test_cancelling_a_credit_note_puts_everything_back(ns, company, factory):
    inv = quick_invoice(ns, qty="10", rate="500")
    note = credit_notes.post_credit_note(credit_notes.save_credit_note(
        invoice=inv, location=ns.godown, date=DAY, user=ns.owner, lines=[(inv.lines.get(), D("5"))], reason="Return"), user=ns.owner)
    with pytest.raises(BusinessRuleError, match="credit note has been posted"):
        invoices.cancel_invoice(inv, user=ns.owner, reason="x")
    credit_notes.cancel_credit_note(note, user=ns.owner, reason="entered by mistake")
    assert stock_at(ns, ns.sku("Black", "M")) == D("90") and inv.lines.get().qty_returned == 0
    assert outstanding_bills(ns.local.customer_ledger)["bills"] == {inv.number: D("5000.00")}
    invoices.cancel_invoice(inv, user=ns.owner, reason="now fine")


# ---------------------------------------------------------------- e-invoice and e-way bill (E4.5, A4)

def test_einvoice_buttons_need_registration_the_switch_a_taxed_invoice_and_a_buyer_gstin(ns, company):
    inv = quick_invoice(ns, ns.far)                                                      # not registered yet
    assert not einvoice.is_available(inv)
    h.gst_on(company)
    from sales.services.common import settings_for

    s = settings_for(company)
    inv = quick_invoice(ns, ns.far)
    assert not einvoice.is_available(inv)                                                # registered, switch still off
    s.einvoice_enabled = True
    s.save()
    assert einvoice.is_available(inv)
    assert not einvoice.is_available(quick_invoice(ns, ns.local))                        # no buyer GSTIN (B2C)
    assert not einvoice.is_available(quick_invoice(ns, ns.far, tax_mode="none", tax_note="LUT"))     # GST waived
    with pytest.raises(BusinessRuleError, match="not available"):
        einvoice.submit(quick_invoice(ns, ns.local), user=ns.owner)


def test_one_click_generates_irn_qr_and_eway_bill_and_a_failure_shows_the_portals_message(ns, company, monkeypatch):
    h.gst_on(company)
    from sales.services.common import settings_for

    s = settings_for(company)
    s.einvoice_enabled = True
    s.save()
    big = quick_invoice(ns, ns.far, qty="100", rate="600")                              # 63,000 incl. GST: needs an e-way bill
    with pytest.raises(BusinessRuleError, match="e-way bill"):
        einvoice.submit(big, user=ns.owner)
    big = einvoice.submit(big, user=ns.owner, vehicle_no="mh12 ab 1")
    assert big.einvoice_status == "generated" and len(big.irn) == 64 and big.qr_text.startswith("IRN:")
    assert big.eway_bill_no and len(big.eway_bill_no) == 12 and big.vehicle_no == "MH12 AB 1"
    payload = einvoice.build_payload(big)
    assert payload["BuyerDtls"]["Gstin"] == h.BUYER_GSTIN and payload["ValDtls"]["IgstVal"] == 3000.0
    assert payload["ItemList"][0]["HsnCd"] == "6112" and payload["ItemList"][0]["GstRt"] == 5.0
    with pytest.raises(BusinessRuleError, match="already been generated"):
        einvoice.submit(big, user=ns.owner, vehicle_no="MH12AB1")
    with pytest.raises(BusinessRuleError, match="e-invoice first"):
        invoices.cancel_invoice(big, user=ns.owner, reason="x")
    einvoice.cancel(big, user=ns.owner, reason="duplicate")
    big.refresh_from_db()
    assert big.einvoice_status == "none" and not big.irn
    invoices.cancel_invoice(big, user=ns.owner, reason="duplicate")

    small = quick_invoice(ns, ns.far, qty="10", rate="500")                              # below the e-way threshold
    small = einvoice.submit(small, user=ns.owner)
    assert small.irn and not small.eway_bill_no

    class Refusing(einvoice.StubProvider):
        def generate_irn(self, payload):
            raise EInvoiceError("2150: Duplicate IRN")

    monkeypatch.setattr(einvoice, "get_provider", lambda: Refusing())
    other = einvoice.submit(quick_invoice(ns, ns.far), user=ns.owner)
    assert other.einvoice_status == "failed" and other.einvoice_error == "2150: Duplicate IRN" and not other.irn


# ---------------------------------------------------------------- factory scoping (BR-23)

def test_a_user_outside_the_factory_can_neither_see_nor_post(ns, company, factory, factory2):
    inv = quick_invoice(ns, post=False)
    o = confirmed_order(ns)
    stranger = make_user("cashier")
    stranger.roles.add(Role.objects.get(name="Billing Clerk"))
    stranger.allowed_factories.add(factory2)
    for model in (SaleInvoice, SaleOrder):
        assert not model.objects.for_user(stranger).exists()
    with pytest.raises(FactoryNotAllowed):
        invoices.post_invoice(inv, user=stranger)
    with pytest.raises(FactoryNotAllowed):
        orders.confirm_order(SaleOrder.objects.get(pk=o.pk), user=stranger)
    with pytest.raises(FactoryNotAllowed):
        invoices.save_invoice(company=company, factory=factory, customer=ns.local, date=DAY, user=stranger, location=ns.godown,
                              lines=[InvoiceLineSpec(ns.sku("Black", "M"), D("1"), D("500"), D("0"))])
