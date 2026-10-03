"""GST and TDS returns support (E9.10): GSTR-1 data, GSTR-3B summary, the tax register and the TDS / TCS report.

GSTR-1 comes from the invoices and credit notes raised in the sales module, because those carry the buyer, the HSN and the
rate of every line. GSTR-3B and the registers come from the tax ledgers themselves, so hand-entered vouchers are in them too.
Nothing is shown as owed unless GST was actually charged: a waived invoice appears only in the nil-rated list."""
from collections import defaultdict
from decimal import Decimal

from django.db.models import Sum

from ledger.models import AccountGroup, Ledger, VoucherLine
from ledger.selectors import posted_lines, q2
from sales.models import SaleCreditNote, SaleCreditNoteLine, SaleInvoice

ZERO = Decimal("0.00")
COMPONENTS = ("igst", "cgst", "sgst")


def _blank():
    return {"taxable": ZERO, "igst": ZERO, "cgst": ZERO, "sgst": ZERO}


def _scope(qs, user, factory, date_from, date_to):
    qs = qs.filter(date__range=(date_from, date_to))
    qs = qs.for_user(user)
    return qs.filter(factory=factory) if factory is not None else qs


def gstr1(company, *, user, factory=None, date_from, date_to):
    invoices = _scope(SaleInvoice.objects.filter(company=company, status="posted"), user, factory, date_from, date_to).select_related(
        "customer").prefetch_related("tax_lines", "lines")
    b2b, b2c, nil, hsn = [], defaultdict(lambda: {**_blank(), "docs": 0}), [], defaultdict(lambda: {**_blank(), "qty": ZERO})
    for inv in invoices:
        if inv.tax_mode == SaleInvoice.TaxMode.NONE or not inv.tax_lines.exists():
            nil.append({"invoice": inv, "taxable": inv.subtotal, "note": inv.tax_note})
            continue
        by_rate = defaultdict(_blank)
        for t in inv.tax_lines.all():
            r = by_rate[t.rate if t.component == "igst" else t.rate * 2]      # CGST + SGST halves make the slab rate
            r["taxable"] = max(r["taxable"], t.taxable)
            r[t.component] += t.amount
        for rate, vals in sorted(by_rate.items()):
            row = {"invoice": inv, "rate": rate, **vals}
            if inv.customer.gstin:
                b2b.append({**row, "gstin": inv.customer.gstin})
            else:
                key = (inv.place_of_supply, rate)
                agg = b2c[key]
                agg["docs"] += 1
                for k in ("taxable", "igst", "cgst", "sgst"):
                    agg[k] += vals[k]
        for line in inv.lines.all():
            row = hsn[(line.hsn, line.gst_rate)]
            row["qty"] += line.qty
            row["taxable"] += line.amount
            for t in line.taxes.all():
                row[t.component] += t.amount

    notes = _scope(SaleCreditNote.objects.filter(company=company, status="posted"), user, factory, date_from, date_to).select_related(
        "customer", "invoice").prefetch_related("lines__taxes", "lines__invoice_line")
    cdn = []
    for n in notes:
        vals, rates = _blank(), set()
        for l in n.lines.all():
            vals["taxable"] += l.amount
            rates.add(l.invoice_line.gst_rate)
            for t in l.taxes.all():
                vals[t.component] += t.amount
            row = hsn[(l.invoice_line.hsn, l.invoice_line.gst_rate)]
            row["qty"] -= l.qty
            row["taxable"] -= l.amount
            for t in l.taxes.all():
                row[t.component] -= t.amount
        if n.gst_total or n.invoice.tax_mode != "none":
            cdn.append({"note": n, "registered": bool(n.customer.gstin), "gstin": n.customer.gstin, **vals})
    docs = {"invoices": invoices.count(), "cancelled": _scope(SaleInvoice.objects.filter(company=company, status="cancelled"), user, factory,
                                                                date_from, date_to).count()}
    b2c_rows = [{"place": place, "rate": rate, **vals} for (place, rate), vals in sorted(b2c.items())]
    hsn_rows = [{"hsn": h, "rate": r, **vals} for (h, r), vals in sorted(hsn.items())]
    totals = _blank()
    for r in b2b + b2c_rows:
        for k in totals:
            totals[k] += r[k]
    for n in cdn:
        for k in totals:
            totals[k] -= n[k]
    return {"b2b": b2b, "b2c": b2c_rows, "cdn": cdn, "hsn": hsn_rows, "nil": nil, "docs": docs, "totals": totals}


def _ledger_net(company, key, user, factory, date_from, date_to):
    agg = posted_lines(user, factory, date_to, date_from).filter(ledger__company=company, ledger__system_key=key).aggregate(
        d=Sum("debit"), c=Sum("credit"))
    return q2(agg["d"]), q2(agg["c"])


def gstr3b(company, *, user, factory=None, date_from, date_to):
    """3.1 outward supplies, reverse charge, 4 input credit, and the tax left to pay, component by component."""
    out, rcm, itc, pay = {}, {}, {}, {}
    for c in COMPONENTS:
        d, cr = _ledger_net(company, f"{c}_output", user, factory, date_from, date_to)
        out[c] = cr - d
        d, cr = _ledger_net(company, f"{c}_rcm", user, factory, date_from, date_to)
        rcm[c] = cr - d
        d, cr = _ledger_net(company, f"{c}_input", user, factory, date_from, date_to)
        itc[c] = d - cr
        pay[c] = out[c] + rcm[c] - itc[c]
    sales = ZERO
    roots = {g.pk: g for g in AccountGroup.objects.filter(company=company)}
    for ledger in Ledger.objects.filter(company=company, group__statement="pl", group__nature="income"):
        node = roots[ledger.group_id]
        while node.parent_id:
            node = roots[node.parent_id]
        if node.name == "Sales":
            d, c = (q2(v) for v in posted_lines(user, factory, date_to, date_from).filter(ledger=ledger).aggregate(
                d=Sum("debit"), c=Sum("credit")).values())
            sales += c - d
    return {"taxable_outward": sales, "output": out, "rcm": rcm, "itc": itc, "payable": pay,
            "output_total": sum(out.values(), ZERO), "rcm_total": sum(rcm.values(), ZERO), "itc_total": sum(itc.values(), ZERO),
            "payable_total": sum(pay.values(), ZERO)}


def tax_register(company, *, user, factory=None, date_from, date_to, kind="gst"):
    """Every voucher line posted to a GST (or TDS / TCS) ledger, with the party on the same voucher."""
    if kind == "gst":
        keys = [f"{c}_{s}" for c in COMPONENTS for s in ("input", "output", "rcm")]
    elif kind == "tds":
        keys = ["tds_payable"]
    else:
        keys = ["tcs_payable"]
    lines = list(posted_lines(user, factory, date_to, date_from).filter(ledger__company=company, ledger__system_key__in=keys)
                 .select_related("voucher", "ledger", "factory").order_by("voucher__date", "voucher_id", "line_no"))
    parties = {}
    party_groups = ("Sundry Debtors", "Sundry Creditors")
    for l in VoucherLine.objects.filter(voucher_id__in={x.voucher_id for x in lines}).select_related("ledger__group__parent"):
        g = l.ledger.group
        if g.name in party_groups or (g.parent and g.parent.name in party_groups):
            parties[l.voucher_id] = l.ledger.name
    rows = [{"date": l.voucher.date, "voucher": l.voucher, "ledger": l.ledger.name, "party": parties.get(l.voucher_id, ""), "factory": l.factory.code,
             "debit": l.debit, "credit": l.credit} for l in lines]
    total_dr = sum((r["debit"] for r in rows), ZERO)
    total_cr = sum((r["credit"] for r in rows), ZERO)
    return {"rows": rows, "debit": total_dr, "credit": total_cr, "net": total_cr - total_dr, "kind": kind}
