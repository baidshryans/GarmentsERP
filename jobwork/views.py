from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from core import viewutils as vu
from core.exceptions import BusinessRuleError
from core.models import Factory, Location
from core.scoping import ScreenPermissionMixin
from core.services.active_factory import in_active, require_active_factory
from masters.models import Party, Process, Size
from production.labels import qr_svg, scan_text
from production.models import Bundle, Lot, LotStep
from production.services import bundles as bundle_service
from tax.models import TaxTemplate

from . import selectors
from .models import (
    ChallanBundle, DailySummary, JobWorkBill, JobWorkChallan, LabourRate, QcResult, Receipt, ReceiptLine,
)
from .services import bills, challans, rates, receipts
from .services import summary as summary_service
from .services.challans import SecondFabricatorWarning
from .services.receipts import Counted
from ledger.settlement import settlement


def _factories(user):
    return Factory.objects.for_user(user).filter(is_active=True)


def _need_factory(request, to):
    """New documents are entered in one factory. In "All factories" mode say so and go back to the list."""
    if request.factory is None:
        messages.error(request, "Choose a single factory in the top bar before entering a document.")
        return redirect(to)
    return None


def _fabricators():
    return Party.objects.filter(is_fabricator=True, is_active=True)


# ================================================================ challans (E8.1)

class ChallanList(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "jobwork.challan"

    def get(self, request):
        qs = in_active(JobWorkChallan.objects.for_user(request.user), request).select_related("party", "lot", "step__process")
        if request.GET.get("status"):
            qs = qs.filter(status=request.GET["status"])
        return render(request, "jobwork/challan_list.html", {
            "challans": qs[:200], "statuses": JobWorkChallan.Status.choices, "status": request.GET.get("status", ""),
            "can_create": request.user.has_screen_perm("jobwork.challan", "create"),
        })


class ChallanNew(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "jobwork.challan"
    screen_action = "create"

    def _ctx(self, request, d):
        lot = Lot.objects.for_user(request.user).select_related("style", "colour").filter(pk=d.get("lot")).first() if d.get("lot") else None
        ctx = {"lot": lot, "d": d, "fabricators": _fabricators(), "factories": _factories(request.user),
               "lots": in_active(Lot.objects.for_user(request.user), request).exclude(status__in=("closed", "completed")).select_related("style", "colour"),
               "kind": d.get("kind", "issue")}
        if lot:
            steps = [s for s in lot.steps.select_related("process", "party") if s.status != "skipped"]
            step = next((s for s in steps if str(s.pk) == d.get("step")), None) or next((s for s in steps if s.assignment == "subcontract" and s.status != "done"), None)
            ctx.update(steps=steps, step=step)
            eligible = []
            for b in lot.bundles.filter(status__in=("cut", "ready", "at_stage", "rework")).select_related(
                    "sku__size", "location__factory", "current_step__process", "lot").order_by("bundle_no"):
                if ctx["kind"] == "rework":
                    if b.status == "rework":
                        eligible.append(b)
                    continue
                if step is None or b.status == "rework":
                    continue
                try:
                    bundle_service.check_entry(b, step, "")
                except BusinessRuleError:
                    continue
                if b.challan_lines.filter(challan__status__in=("draft", "issued", "partly_received")).exists():
                    continue
                eligible.append(b)
            for b in eligible:
                b.scan = scan_text(b)
            ctx["bundles"] = eligible
        return ctx

    def get(self, request):
        return render(request, "jobwork/challan_form.html", self._ctx(request, request.GET))

    def post(self, request):
        p = request.POST
        ctx = self._ctx(request, p)
        try:
            lot, step = ctx["lot"], ctx.get("step")
            if lot is None or step is None:
                raise BusinessRuleError("Choose the lot and the step first.")
            ids = p.getlist("bundle")
            challan = challans.create_challan(
                company=vu.company(), factory=get_object_or_404(_factories(request.user), pk=p.get("factory") or lot.factory_id),
                party=get_object_or_404(Party, pk=p.get("party"), is_fabricator=True), lot=lot, step=step,
                bundles=list(Bundle.objects.filter(pk__in=ids, lot=lot)), date=vu.day(p.get("date"), default=timezone.localdate()),
                user=request.user, expected_date=vu.day(p.get("expected_date")) if p.get("expected_date") else None,
                kind=p.get("kind", "issue"), remarks=p.get("remarks", ""), confirm_second_fabricator=p.get("confirm_second") == "on")
        except SecondFabricatorWarning as exc:
            messages.warning(request, str(exc))
            ctx["need_confirm"] = True
            return render(request, "jobwork/challan_form.html", ctx)
        except (ValueError, BusinessRuleError) as exc:
            vu.report(request, exc)
            return render(request, "jobwork/challan_form.html", ctx)
        messages.success(request, "Challan saved as a draft. Check it, then issue it.")
        return redirect("challan_detail", pk=challan.pk)


class ChallanDetail(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "jobwork.challan"

    def _ch(self, request, pk):
        return get_object_or_404(JobWorkChallan.objects.for_user(request.user).select_related("party", "lot", "step__process", "factory"), pk=pk)

    def get(self, request, pk):
        ch = self._ch(request, pk)
        return render(request, "jobwork/challan_detail.html", {
            "ch": ch, "lines": ch.bundles.select_related("bundle__sku__size", "bundle__sku__colour"), "trims": ch.trims.select_related("material"),
            "receipts": ch.receipts.all(), "can_edit": request.user.has_screen_perm("jobwork.challan", "edit"),
            "can_receive": request.user.has_screen_perm("jobwork.receipt", "create"),
            "total_pieces": sum(l.qty_issued for l in ch.bundles.all()),
        })

    def post(self, request, pk):
        ch = self._ch(request, pk)
        if not request.user.has_screen_perm("jobwork.challan", "edit"):
            raise PermissionDenied
        try:
            if request.POST.get("action") == "issue":
                ch = challans.issue_challan(ch, user=request.user)
                messages.success(request, f"{ch.number} issued. The bundles are now with {ch.party.name}.")
            elif request.POST.get("action") == "discard":
                challans.cancel_draft(ch, user=request.user)
                messages.success(request, "Draft discarded.")
                return redirect("challan_list")
        except BusinessRuleError as exc:
            messages.error(request, str(exc))
        return redirect("challan_detail", pk=pk)


class ChallanPrint(LoginRequiredMixin, ScreenPermissionMixin, View):
    """Printed challan: English, with the challan number and a QR, plain black on white (E8.1)."""

    screen_code = "jobwork.challan"

    def get(self, request, pk):
        ch = get_object_or_404(JobWorkChallan.objects.for_user(request.user).select_related("party", "lot__style", "lot__colour", "factory", "step__process", "company"), pk=pk)
        import segno

        qr = segno.make(f"JWC:{ch.number or ch.pk}", error="m").svg_inline(scale=3, border=1, dark="#000", light="#fff")
        lines = list(ch.bundles.select_related("bundle__sku__size"))
        return render(request, "jobwork/challan_print.html", {
            "ch": ch, "lines": lines, "trims": ch.trims.select_related("material"), "qr": qr,
            "total": sum(l.qty_issued for l in lines),
        })


# ================================================================ receipts and QC (E8.2, E8.3)

class ReceiptList(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "jobwork.receipt"

    def get(self, request):
        qs = in_active(Receipt.objects.for_user(request.user), request).select_related("challan__party", "challan__lot")
        return render(request, "jobwork/receipt_list.html", {
            "receipts": qs[:200], "pending_qc": ReceiptLine.objects.filter(qc_done=False, receipt__in=qs.exclude(status="pending_approval")).count(),
        })


class ReceiptNew(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "jobwork.receipt"
    screen_action = "create"

    def _ctx(self, request, challan, d=None):
        lines = [cb for cb in challan.bundles.select_related("bundle__sku__size", "bundle__sku__colour")
                 if not (cb.qty_received or cb.qty_shortage)]
        for cb in lines:
            cb.scan = scan_text(cb.bundle)
        return {"ch": challan, "lines": lines, "trims": [t for t in challan.trims.select_related("material")],
                "d": d or {}, "locations": Location.objects.filter(factory=challan.factory, is_active=True).exclude(loc_type__in=("transit", "fabricator", "rejects"))}

    def _challan(self, request, pk):
        return get_object_or_404(JobWorkChallan.objects.for_user(request.user).select_related("party", "lot", "factory", "step__process"), pk=pk)

    def get(self, request, pk):
        return render(request, "jobwork/receipt_form.html", self._ctx(request, self._challan(request, pk)))

    def post(self, request, pk):
        ch = self._challan(request, pk)
        p = request.POST
        try:
            counts = []
            for cb in ch.bundles.all():
                if p.get(f"use_{cb.pk}"):
                    counts.append(Counted(cb, vu.whole(p.get(f"count_{cb.pk}"), f"Pieces counted for {cb.bundle.bundle_no}")))
            trims = {}
            for t in ch.trims.all():
                returned, missing = vu.dec(p.get(f"returned_{t.pk}"), "Returned", Decimal("0")), vu.dec(p.get(f"missing_{t.pk}"), "Missing", Decimal("0"))
                if returned or missing:
                    trims[t] = (returned, missing)
            location = Location.objects.filter(pk=p.get("location"), factory=ch.factory).first() if p.get("location") else None
            receipt = receipts.create_receipt(challan=ch, counts=counts, user=request.user, location=location, trims=trims,
                                              date=vu.day(p.get("date"), default=timezone.localdate()))
        except (ValueError, BusinessRuleError) as exc:
            vu.report(request, exc)
            return render(request, "jobwork/receipt_form.html", self._ctx(request, ch, p))
        if receipt.status == "pending_approval":
            messages.warning(request, "You counted more than was issued. The owner must approve it before the goods are received (BR-03).")
        else:
            messages.success(request, f"{receipt.number} received. Now check the quality.")
        return redirect("receipt_detail", pk=receipt.pk)


class ReceiptDetail(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "jobwork.receipt"

    def _rec(self, request, pk):
        return get_object_or_404(Receipt.objects.for_user(request.user).select_related("challan__party", "challan__lot", "challan__step__process"), pk=pk)

    def get(self, request, pk):
        r = self._rec(request, pk)
        user = request.user
        lines = list(r.lines.select_related("challan_bundle__bundle__sku__size", "challan_bundle__bundle__sku__colour"))
        for l in lines:
            l.qc_result = getattr(l, "qc", None) if hasattr(l, "qc") else None
        return render(request, "jobwork/receipt_detail.html", {
            "r": r, "lines": lines, "trims": r.trims.select_related("challan_trim__material"),
            "can_approve": user.has_screen_perm("jobwork.receipt", "approve"),
            "can_qc": user.has_screen_perm("jobwork.qc", "create"),
        })

    def post(self, request, pk):
        r = self._rec(request, pk)
        p, user = request.POST, request.user
        try:
            if p.get("action") == "approve":
                receipts.approve_receipt(r, user=user)
                messages.success(request, "Over-receipt approved and the goods received.")
            elif p.get("action") == "qc":
                if not user.has_screen_perm("jobwork.qc", "create"):
                    raise PermissionDenied
                line = get_object_or_404(ReceiptLine, pk=p.get("line"), receipt=r)
                receipts.record_qc(
                    receipt_line=line, accepted=vu.whole(p.get("accepted"), "Accepted", 0), rejected=vu.whole(p.get("rejected"), "Rejected", 0),
                    rework=vu.whole(p.get("rework"), "Rework", 0), user=user, reject_reason=p.get("reason", ""),
                    destination=p.get("destination", "rejects"))
                messages.success(request, "QC recorded.")
        except (ValueError, BusinessRuleError) as exc:
            vu.report(request, exc)
        return redirect("receipt_detail", pk=pk)


# ================================================================ labour rates (JOB-06)

class RateList(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "jobwork.rate"

    def get(self, request):
        return render(request, "jobwork/rate_list.html", {
            "rates": LabourRate.objects.select_related("party", "process").prefetch_related("addons", "sizes__size"),
            "can_create": request.user.has_screen_perm("jobwork.rate", "create"),
        })


class RateNew(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "jobwork.rate"
    screen_action = "create"

    def _ctx(self, d=None):
        return {"fabricators": Party.objects.filter(is_active=True).filter(is_fabricator=True) | Party.objects.filter(is_vendor=True, is_active=True),
                "processes": Process.objects.filter(is_active=True), "sizes": Size.objects.filter(is_active=True),
                "types": LabourRate.Type.choices, "d": d or {}}

    def get(self, request):
        return render(request, "jobwork/rate_form.html", self._ctx())

    def post(self, request):
        p = request.POST
        try:
            addons = [(n.strip(), vu.dec(a, "Add-on amount")) for n, a in zip(p.getlist("addon_name"), p.getlist("addon_amount")) if n.strip()]
            size_rates = {s: vu.dec(p.get(f"size_{s.pk}"), "Size rate") for s in Size.objects.all() if p.get(f"size_{s.pk}", "").strip()}
            rates.save_rate(
                party=get_object_or_404(Party, pk=p.get("party")), process=get_object_or_404(Process, pk=p.get("process")),
                rate_type=p.get("rate_type"), effective_from=vu.day(p.get("effective_from")),
                base_rate=vu.dec(p.get("base_rate"), "Rate", Decimal("0")), flat_amount=vu.dec(p.get("flat_amount"), "Flat amount", Decimal("0")),
                rework_rate=vu.dec(p.get("rework_rate"), "Rework rate", Decimal("0")), addons=addons, size_rates=size_rates)
        except (ValueError, BusinessRuleError) as exc:
            vu.report(request, exc)
            return render(request, "jobwork/rate_form.html", self._ctx(p))
        messages.success(request, "Rate saved. It applies to challans issued from its date.")
        return redirect("rate_list")


# ================================================================ labour bills (E8.4)

class BillList(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "jobwork.bill"

    def get(self, request):
        qs = in_active(JobWorkBill.objects.for_user(request.user), request).select_related("party", "factory")
        return render(request, "jobwork/bill_list.html", {"bills": qs[:200], "can_create": request.user.has_screen_perm("jobwork.bill", "create")})


class BillNew(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "jobwork.bill"
    screen_action = "create"

    def _ctx(self, request, d):
        party = Party.objects.filter(pk=d.get("party")).first() if d.get("party") else None
        factory = request.factory
        ctx = {"fabricators": _fabricators(), "party": party, "factory": factory, "d": d,
               "tds": TaxTemplate.objects.filter(kind="tds", is_active=True)}
        if party and factory:
            rows = []
            for r in bills.unbilled_qc(party, factory):
                amount, rate = bills._amount_for(r)
                rows.append({"r": r, "amount": amount, "rate": rate})
            ctx["rows"] = rows
            ctx["deductions"] = bills.pending_deductions(party, factory)
        return ctx

    def get(self, request):
        if back := _need_factory(request, "bill_list"):
            return back
        return render(request, "jobwork/bill_form.html", self._ctx(request, request.GET))

    def post(self, request):
        p = request.POST
        try:
            party = get_object_or_404(Party, pk=p.get("party"))
            factory = require_active_factory(request)
            picked = [get_object_or_404(QcResult, pk=k[3:]) for k in p if k.startswith("qc_")]
            all_pending = bills.pending_deductions(party, factory)
            wanted = {k[4:] for k in p if k.startswith("ded_")}
            chosen = [d for d in all_pending if (str(d[5].pk) if d[5] else f"t{d[6].pk}") in wanted]
            bill = bills.create_bill(
                company=vu.company(), factory=factory, party=party, date=vu.day(p.get("date"), default=timezone.localdate()), user=request.user,
                qc_results=picked, deductions=chosen,
                tds_template=TaxTemplate.objects.filter(pk=p["tds_template"], kind="tds").first() if p.get("tds_template") else None,
                notes=p.get("notes", ""))
        except (ValueError, BusinessRuleError) as exc:
            vu.report(request, exc)
            return render(request, "jobwork/bill_form.html", self._ctx(request, p))
        messages.success(request, "Bill saved as a draft. Check it, then post it.")
        return redirect("bill_detail", pk=bill.pk)


class BillDetail(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "jobwork.bill"

    def _bill(self, request, pk):
        return get_object_or_404(JobWorkBill.objects.for_user(request.user).select_related("party", "factory", "tds_template", "voucher"), pk=pk)

    def get(self, request, pk):
        b = self._bill(request, pk)
        return render(request, "jobwork/bill_detail.html", {
            "b": b, "lines": b.lines.select_related("challan", "lot"), "deductions": b.deduction_lines.select_related("challan"),
            "can_edit": request.user.has_screen_perm("jobwork.bill", "edit"), "can_cancel": request.user.has_screen_perm("jobwork.bill", "cancel"),
            "settle": settlement(request.user, ledger=b.party.payable_ledger, reference=b.number, direction="pay",
                                 narration=f"Paid against labour bill {b.number}")
            if b.status == "posted" and b.party.payable_ledger_id else None,
        })

    def post(self, request, pk):
        b = self._bill(request, pk)
        action, user = request.POST.get("action"), request.user
        try:
            if action == "post":
                if not user.has_screen_perm("jobwork.bill", "edit"):
                    raise PermissionDenied
                b = bills.post_bill(b, user=user)
                messages.success(request, f"{b.number} posted to the fabricator's account.")
            elif action == "cancel":
                if not user.has_screen_perm("jobwork.bill", "cancel"):
                    raise PermissionDenied
                bills.cancel_bill(b, user=user, reason=request.POST.get("reason", ""))
                messages.success(request, "Bill cancelled. Its accepted pieces can be billed again.")
        except BusinessRuleError as exc:
            messages.error(request, str(exc))
        return redirect("bill_detail", pk=pk)


# ================================================================ reports (JOB-05, JOB-08, JOB-12)

class DailySummaryView(LoginRequiredMixin, ScreenPermissionMixin, View):
    """The day's picture of every fabricator, per factory (E8.8). Built by the daily_summary command; "Build now" redoes a day."""

    screen_code = "jobwork.report"

    def _day(self, text):
        try:
            return vu.day(text, default=timezone.localdate())
        except ValueError:
            return timezone.localdate()

    def get(self, request):
        on_date = self._day(request.GET.get("date"))
        found = in_active(DailySummary.objects.for_user(request.user), request).filter(date=on_date).select_related("factory")
        blocks = [{"summary": s, "rows": s.rows.select_related("party"), "totals": summary_service.totals(s),
                   "text": summary_service.as_text(s)} for s in found]
        return render(request, "jobwork/daily_summary.html", {
            "date": on_date, "blocks": blocks, "can_build": request.user.has_screen_perm("jobwork.report", "edit"),
            "factories": request.active_factories})

    def post(self, request):
        if not request.user.has_screen_perm("jobwork.report", "edit"):
            raise PermissionDenied
        on_date = self._day(request.POST.get("date"))
        try:
            for factory in request.active_factories:
                summary_service.build_summary(factory, on_date, user=request.user)
            messages.success(request, f"Summary built for {on_date:%d %b %Y}.")
        except BusinessRuleError as exc:
            vu.report(request, exc)
        return redirect(f"{reverse('daily_summary')}?date={on_date.isoformat()}")


class Reports(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "jobwork.report"

    def get(self, request):
        party = Party.objects.filter(pk=request.GET.get("party"), is_fabricator=True).first() if request.GET.get("party") else None
        return render(request, "jobwork/reports.html", {
            "fabricators": _fabricators(), "party": party,
            "ledger": selectors.fabricator_ledger(request.user, party) if party else None,
            "shortages": selectors.shortage_report(request.user), "ageing": selectors.ageing(request.user),
        })
