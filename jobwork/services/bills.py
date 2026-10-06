"""The fabricator's labour bill (E8.4, JOB-07, JOB-11, BR-17). Built from checked pieces that have not been paid
before: the accepted ones, or every piece received, as the challan's pay basis says. Less deductions for shortage and
missing trims, unless the owner bears them. TDS is deducted only if a TDS template is chosen.

Voucher: Dr Work in Progress (gross - deductions), Cr TDS Payable, Cr Fabricator (bill-wise). The same net amount goes
into each lot's cost as job work.
"""
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Exists, OuterRef, Q

from core.exceptions import BusinessRuleError
from core.scoping import assert_factory_access
from core.services.numbering import next_document_number
from jobwork.models import (
    JobWorkBill, JobWorkBillDeduction, JobWorkBillLine, JobWorkChallan, JobWorkDeductionWaiver, PayBasis, QcResult,
    ReceiptLine, ReceiptTrim,
)
from ledger.services.posting import AllocationSpec, LineSpec, post_voucher, reverse_voucher
from production.models import LotCostEntry
from production.services import costing
from tax import calc

ZERO = Decimal("0.00")


def unbilled_qc(party, factory=None):
    """QC results of this fabricator with payable pieces that no bill has paid yet."""
    qs = QcResult.objects.filter(line__challan_bundle__challan__party=party, bill_line__isnull=True, pay_qty__gt=0)
    if factory is not None:
        qs = qs.filter(line__challan_bundle__challan__factory=factory)
    return qs.select_related("line__challan_bundle__challan", "line__challan_bundle__bundle", "line__challan_bundle__bundle__sku")


def pending_deductions(party, factory=None):
    """Shortage and missing trims not yet recovered on a bill, and not waived by the owner:
    [(kind, challan, lot, description, amount, receipt_line, receipt_trim)]."""
    active = JobWorkBillDeduction.objects.exclude(bill__status="cancelled")
    out = []
    lines = ReceiptLine.objects.filter(challan_bundle__challan__party=party, shortage_qty__gt=0, shortage_value__gt=0,
                                       waiver__isnull=True)
    if factory is not None:
        lines = lines.filter(challan_bundle__challan__factory=factory)
    for rl in lines.select_related("challan_bundle__challan", "challan_bundle__bundle", "receipt"):
        if active.filter(source_receipt_line=rl).exists():
            continue
        ch = rl.challan_bundle.challan
        out.append((JobWorkBillDeduction.Kind.SHORTAGE, ch, ch.lot,
                    f"Shortage of {rl.shortage_qty} pieces, bundle {rl.challan_bundle.bundle.bundle_no}", rl.shortage_value, rl, None))
    trims = ReceiptTrim.objects.filter(challan_trim__challan__party=party, qty_missing__gt=0, waiver__isnull=True)
    if factory is not None:
        trims = trims.filter(challan_trim__challan__factory=factory)
    for rt in trims.select_related("challan_trim__challan", "challan_trim__material"):
        if active.filter(source_receipt_trim=rt).exists():
            continue
        ch = rt.challan_trim.challan
        amount = costing.r2(rt.challan_trim.unit_cost * rt.qty_missing)
        if amount > 0:
            out.append((JobWorkBillDeduction.Kind.MISSING_TRIMS, ch, ch.lot,
                        f"Missing {rt.qty_missing.normalize():f} {rt.challan_trim.material.name}", amount, None, rt))
    return out


def takes_by_default(deduction) -> bool:
    """Is this pending deduction taken unless the user says otherwise? Not a shortage on a challan paid on pieces
    received: there the owner bears lost pieces, so it starts unticked."""
    kind, challan = deduction[0], deduction[1]
    return not (kind == JobWorkBillDeduction.Kind.SHORTAGE and challan.pay_basis == PayBasis.RECEIVED)


def deduction_key(deduction) -> str:
    """How the bill form names a pending deduction: its receipt line, or `t` and its receipt trim."""
    return str(deduction[5].pk) if deduction[5] else f"t{deduction[6].pk}"


def amount_for(result):
    """(amount, rate) payable for one QC result: its payable pieces at the rate fixed on the challan; flat-per-lot
    challans pay pro rata to the pieces issued."""
    cb = result.line.challan_bundle
    challan = cb.challan
    if challan.rate_type == "D" and challan.kind == "issue":
        total_issued = sum(b.qty_issued for b in challan.bundles.all())
        return costing.r2(challan.flat_amount * min(result.pay_qty, cb.qty_issued) / total_issued), ZERO
    return costing.r2(result.rate * result.pay_qty), result.rate


_amount_for = amount_for


@transaction.atomic
def create_bill(*, company, factory, party, date, user, qc_results=None, deductions=None, tds_template=None, notes="") -> JobWorkBill:
    """Draft bill. Defaults to every unpaid payable result of the fabricator in the factory and the pending
    deductions that are taken by default (see `takes_by_default`)."""
    assert_factory_access(user, factory)
    if not party.is_fabricator and not party.is_vendor:
        raise BusinessRuleError(f"{party.name} is not a fabricator.")
    if party.payable_ledger_id is None:
        raise BusinessRuleError(f"{party.name} has no payable ledger.")
    results = list(qc_results) if qc_results is not None else list(unbilled_qc(party, factory))
    if not results:
        raise BusinessRuleError("There are no checked pieces waiting to be paid for this fabricator (JOB-07).")
    for r in results:
        r = QcResult.objects.select_related("line__challan_bundle__challan").get(pk=r.pk)
        ch = r.line.challan_bundle.challan
        if ch.party_id != party.pk or ch.factory_id != factory.pk:
            raise BusinessRuleError("A QC result belongs to a different fabricator or factory.")
        if r.bill_line_id or r.pay_qty <= 0:
            raise BusinessRuleError("Only payable pieces that have not been paid before can be billed.")
    picked = [d for d in pending_deductions(party, factory) if takes_by_default(d)] if deductions is None else list(deductions)
    if tds_template is not None and tds_template.kind != "tds":
        raise BusinessRuleError("Choose a TDS template for TDS.")

    bill = JobWorkBill.objects.create(company=company, factory=factory, party=party, date=date, tds_template=tds_template,
                                      notes=notes, created_by=user)
    gross = ZERO
    grouped = {}
    for r in results:
        r = QcResult.objects.select_related("line__challan_bundle__challan__lot", "line__challan_bundle__challan__step__process").get(pk=r.pk)
        ch = r.line.challan_bundle.challan
        amount, rate = amount_for(r)
        key = (ch.pk, rate)
        g = grouped.setdefault(key, {"challan": ch, "rate": rate, "qty": 0, "amount": ZERO, "results": []})
        g["qty"] += r.pay_qty
        g["amount"] += amount
        g["results"].append(r)
    for g in grouped.values():
        ch = g["challan"]
        kind = "rework " if ch.kind == "rework" else ""
        line = JobWorkBillLine.objects.create(
            bill=bill, challan=ch, lot=ch.lot, qty=g["qty"], rate=g["rate"], amount=g["amount"],
            description=f"{kind}{ch.step.process.name} on lot {ch.lot.lot_no} ({ch.number})")
        for r in g["results"]:
            r.bill_line = line
            r.save(update_fields=["bill_line"])
        gross += g["amount"]
    total_deductions = ZERO
    for kind, ch, lot, text, amount, rl, rt in picked:
        JobWorkBillDeduction.objects.create(bill=bill, challan=ch, lot=lot, kind=kind, description=text, amount=amount,
                                            source_receipt_line=rl, source_receipt_trim=rt)
        total_deductions += amount
    base = gross - total_deductions
    if base < 0:
        raise BusinessRuleError("The deductions are more than the amount earned; settle them separately first.")
    tds = sum((t.amount for t in calc.compute(tds_template, base)), ZERO) if tds_template else ZERO
    bill.gross, bill.deductions, bill.tds, bill.net = gross, total_deductions, tds, base - tds
    bill.save()
    return bill


@transaction.atomic
def post_bill(bill, *, user) -> JobWorkBill:
    bill = JobWorkBill.objects.select_related("company", "factory", "party").get(pk=bill.pk)
    assert_factory_access(user, bill.factory)
    if bill.status != JobWorkBill.Status.DRAFT:
        raise BusinessRuleError("This bill has already been posted or cancelled.")
    company, factory, party = bill.company, bill.factory, bill.party
    cost_base = bill.gross - bill.deductions
    number = next_document_number(factory=factory, doc_type="labour_bill", on_date=bill.date)
    due = bill.date + timedelta(days=party.credit_days)
    lines = []
    if cost_base > 0:
        lines.append(LineSpec(ledger=costing.ledger_for(company, "stock_wip"), debit=cost_base,
                              narration="Job work capitalised into the lots"))
    if bill.tds > 0:
        lines.append(LineSpec(ledger=costing.ledger_for(company, "tds_payable"), credit=bill.tds, narration="TDS deducted"))
    lines.append(LineSpec(ledger=party.payable_ledger, credit=bill.net, narration=f"Labour bill {number}",
                          allocations=(AllocationSpec("new", bill.net, number, due),)))
    voucher = post_voucher(
        company=company, factory=factory, voucher_type="job_work_bill", date=bill.date, lines=lines, user=user,
        narration=f"Labour bill {number}: {party.name}", source=bill)
    per_lot = {}
    for l in bill.lines.select_related("lot"):
        per_lot[l.lot_id] = per_lot.get(l.lot_id, ZERO) + l.amount
    lots = {l.lot_id: l.lot for l in bill.lines.select_related("lot")}
    for d in bill.deduction_lines.select_related("lot"):
        per_lot[d.lot_id] = per_lot.get(d.lot_id, ZERO) - d.amount
        lots[d.lot_id] = d.lot
    for lot_id, amount in per_lot.items():
        if amount != 0:
            costing.add_cost(lot=lots[lot_id], factory=factory, kind=LotCostEntry.Kind.JOBWORK, amount=amount,
                             date=bill.date, note=f"Labour bill {number}", source=bill, voucher=voucher)
    bill.number, bill.status, bill.voucher = number, JobWorkBill.Status.POSTED, voucher
    bill.save()
    for ch in JobWorkChallan.objects.filter(pk__in={l.challan_id for l in bill.lines.all()}):
        _refresh_billed(ch)
    return bill


def _refresh_billed(challan):
    from jobwork.services.receipts import _refresh_challan

    challan = JobWorkChallan.objects.get(pk=challan.pk)
    everything_in = all(cb.qty_received or cb.qty_shortage for cb in challan.bundles.all())
    unpaid = QcResult.objects.filter(line__challan_bundle__challan=challan, bill_line__isnull=True, pay_qty__gt=0).exists()
    pending_qc = ReceiptLine.objects.filter(challan_bundle__challan=challan, qc_done=False).exists()
    rework_open = challan.bundles.filter(bundle__status="rework").exists()
    if everything_in and not unpaid and not pending_qc and not rework_open and challan.bill_lines.exists():
        challan.status = JobWorkChallan.Status.BILLED
        challan.save(update_fields=["status"])
    else:
        _refresh_challan(challan)


@transaction.atomic
def waive_deduction(*, user, reason, receipt_line=None, receipt_trim=None) -> JobWorkDeductionWaiver:
    """The owner bears a shortage or missing trims: it stops being offered as a deduction. Nothing is posted; the
    cost stays in the lot and is carried by the pieces that are left."""
    if (receipt_line is None) == (receipt_trim is None):
        raise BusinessRuleError("Choose one shortage or one line of missing trims to waive.")
    challan = receipt_line.challan_bundle.challan if receipt_line is not None else receipt_trim.challan_trim.challan
    assert_factory_access(user, challan.factory)
    if not user.has_screen_perm("jobwork.bill", "approve"):
        raise BusinessRuleError("Only the owner can waive a deduction.")
    if not reason.strip():
        raise BusinessRuleError("Give a reason for waiving the deduction.")
    source = {"source_receipt_line": receipt_line} if receipt_line is not None else {"source_receipt_trim": receipt_trim}
    if JobWorkBillDeduction.objects.exclude(bill__status="cancelled").filter(**source).exists():
        raise BusinessRuleError("This deduction is already on a labour bill.")
    if JobWorkDeductionWaiver.objects.filter(receipt_line=receipt_line, receipt_trim=receipt_trim).exists():
        raise BusinessRuleError("This deduction has already been waived.")
    return JobWorkDeductionWaiver.objects.create(receipt_line=receipt_line, receipt_trim=receipt_trim,
                                                 reason=reason.strip()[:255], waived_by=user)


@transaction.atomic
def cancel_bill(bill, *, user, reason) -> JobWorkBill:
    bill = JobWorkBill.objects.select_related("factory").get(pk=bill.pk)
    assert_factory_access(user, bill.factory)
    if not reason.strip():
        raise BusinessRuleError("Give a reason to cancel the bill.")
    if bill.status == JobWorkBill.Status.DRAFT:
        QcResult.objects.filter(bill_line__bill=bill).update(bill_line=None)
        bill.status = JobWorkBill.Status.CANCELLED
        bill.save(update_fields=["status"])
        return bill
    if bill.status != JobWorkBill.Status.POSTED:
        raise BusinessRuleError("This bill is already cancelled.")
    from django.utils import timezone

    when = max(timezone.localdate(), bill.date)
    reverse_voucher(bill.voucher, user=user, reason=f"Labour bill cancelled: {reason.strip()}", date=when)
    for e in LotCostEntry.objects.filter(source_type=bill._meta.label_lower, source_id=bill.pk):
        costing.add_cost(lot=e.lot, factory=e.factory, kind=e.kind, amount=-e.amount, date=when,
                         note=f"Bill {bill.number} cancelled", source=bill)
    QcResult.objects.filter(bill_line__bill=bill).update(bill_line=None)
    bill.status = JobWorkBill.Status.CANCELLED
    bill.notes = f"Cancelled: {reason.strip()}"[:255]
    bill.save()
    for ch in JobWorkChallan.objects.filter(pk__in={l.challan_id for l in bill.lines.all()}):
        ch = JobWorkChallan.objects.get(pk=ch.pk)
        if ch.status == JobWorkChallan.Status.BILLED:
            ch.status = JobWorkChallan.Status.RECEIVED
            ch.save(update_fields=["status"])
    return bill
