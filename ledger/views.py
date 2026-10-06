from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from core.crud import ObjectDelete
from core.exceptions import BusinessRuleError
from core.services.active_factory import require_active_factory
from core.models import Company, Factory
from core.services.active_factory import need_factory, require_active_factory
from core.scoping import ScreenPermissionMixin

from .forms import GroupForm, LedgerForm
from .models import AccountGroup, Ledger, Voucher, VoucherType
from .selectors import ledger_position, outstanding_bills, trial_balance
from .services.opening import OpeningEntry, post_opening_balances
from .services.manual import MANUAL_TYPES, Row, cash_bank_ledgers, parse_amount, post_manual_voucher
from .services.party_voucher import PartyRow, post_party_voucher
from .services.posting import reverse_voucher

ZERO = Decimal("0.00")


def _company():
    return Company.objects.get(setup_complete=True)


# ---------------- chart of accounts (SYS-05) ----------------

class ChartView(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "ledger.chart"

    def get(self, request):
        company = _company()
        groups = AccountGroup.objects.filter(company=company).prefetch_related("ledgers")
        by_parent = {}
        for g in groups:
            by_parent.setdefault(g.parent_id, []).append(g)
        rows = []

        def walk(parent_id, depth):
            for g in by_parent.get(parent_id, []):
                rows.append({"kind": "group", "obj": g, "depth": depth})
                for l in sorted(g.ledgers.all(), key=lambda l: l.name):
                    rows.append({"kind": "ledger", "obj": l, "depth": depth + 1})
                walk(g.pk, depth + 1)

        walk(None, 0)
        return render(request, "ledger/chart.html", {"rows": rows})


class LedgerList(LoginRequiredMixin, ScreenPermissionMixin, View):
    """Every ledger in one flat list: search by name or code, filter by group or status, then edit or delete."""

    screen_code = "ledger.chart"

    def get(self, request):
        company = _company()
        q, status = request.GET.get("q", "").strip(), request.GET.get("status", "active")
        group = request.GET.get("group", "")
        qs = Ledger.objects.filter(company=company).select_related("group")
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q) | Q(group__name__icontains=q))
        if group.isdigit():
            qs = qs.filter(group_id=int(group))
        if status == "active":
            qs = qs.filter(is_active=True)
        elif status == "inactive":
            qs = qs.filter(is_active=False)
        total = qs.count()
        return render(request, "ledger/ledger_list.html", {
            "ledgers": qs.order_by("name")[:500], "total": total, "q": q, "status": status, "group": group,
            "groups": AccountGroup.objects.filter(company=company).order_by("name")})


class GroupSave(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "ledger.chart"
    screen_action = "edit"

    def dispatch(self, request, *args, **kwargs):
        if kwargs.get("pk") is None:
            self.screen_action = "create"
        return super().dispatch(request, *args, **kwargs)

    def _obj(self, pk):
        return get_object_or_404(AccountGroup, pk=pk, company=_company()) if pk else None

    def get(self, request, pk=None):
        form = GroupForm(instance=self._obj(pk), company=_company())
        return render(request, "core/form.html", self._ctx(form, pk))

    def post(self, request, pk=None):
        form = GroupForm(request.POST, instance=self._obj(pk), company=_company())
        if form.is_valid():
            form.save()
            messages.success(request, "Group saved.")
            return redirect("chart_of_accounts")
        return render(request, "core/form.html", self._ctx(form, pk))

    @staticmethod
    def _ctx(form, pk):
        return {"form": form, "title": "Edit account group" if pk else "New account group",
                "intro": "A group is a heading in the chart of accounts, such as Current Assets or Sundry Debtors. "
                         "It holds ledgers and other groups, and carries no balance of its own.",
                "cancel_url": "chart_of_accounts"}


class LedgerSave(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "ledger.chart"
    screen_action = "edit"

    def dispatch(self, request, *args, **kwargs):
        if kwargs.get("pk") is None:
            self.screen_action = "create"
        return super().dispatch(request, *args, **kwargs)

    def _obj(self, pk):
        return get_object_or_404(Ledger, pk=pk, company=_company()) if pk else None

    def get(self, request, pk=None):
        form = LedgerForm(instance=self._obj(pk), company=_company())
        return render(request, "core/form.html", self._ctx(form, pk))

    def post(self, request, pk=None):
        form = LedgerForm(request.POST, instance=self._obj(pk), company=_company())
        if form.is_valid():
            form.save()
            messages.success(request, "Ledger saved. A ledger with entries can be deactivated but never deleted.")
            return redirect("ledger_list")
        return render(request, "core/form.html", self._ctx(form, pk))

    @staticmethod
    def _ctx(form, pk):
        return {"form": form, "title": "Edit ledger" if pk else "New ledger",
                "intro": "A ledger is an account that vouchers post to, such as a bank account, a customer or an expense. "
                         "It sits inside a group. To add a heading instead, create a group.",
                "cancel_url": "ledger_list"}


class GroupDelete(ObjectDelete):
    screen_code, success_url_name, noun = "ledger.chart", "chart_of_accounts", "account group"

    def get_object(self, request, pk):
        return get_object_or_404(AccountGroup, pk=pk, company=_company())

    def blocked_reason(self, obj):
        return "System groups are part of the standard chart and cannot be deleted." if obj.is_system else None


class LedgerDelete(ObjectDelete):
    screen_code, success_url_name, noun = "ledger.chart", "ledger_list", "ledger"

    def get_object(self, request, pk):
        return get_object_or_404(Ledger, pk=pk, company=_company())

    def blocked_reason(self, obj):
        if obj.is_system:
            return "System ledgers are used by automatic postings and cannot be deleted."
        if obj.lines.exists():
            return f"'{obj.name}' has entries, so it cannot be deleted. Mark it inactive instead."
        return None


# ---------------- vouchers (read, reverse) ----------------

class VoucherList(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "ledger.voucher"

    def get(self, request):
        qs = Voucher.objects.for_user(request.user).select_related("factory")
        vtype = request.GET.get("type")
        status = request.GET.get("status")
        if request.factory:
            qs = qs.filter(factory=request.factory)
        if vtype:
            qs = qs.filter(voucher_type=vtype)
        if status:
            qs = qs.filter(status=status)
        q = request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(Q(number__icontains=q) | Q(vendor_invoice_no__icontains=q))
        return render(request, "ledger/voucher_list.html", {
            "vouchers": qs[:200],
            "types": VoucherType.choices, "f": {"type": vtype, "status": status, "q": q},
            "can_create": request.user.has_screen_perm("ledger.voucher", "create"),
        })


SOURCE_PAGES = {   # source document -> (what to call it, url name)
    "purchases.grn": ("GRN", "grn_detail"), "purchases.purchaseinvoice": ("Purchase invoice", "invoice_detail"),
    "purchases.debitnote": ("Debit note", "debitnote_detail"), "sales.saleinvoice": ("Sale invoice", "saleinvoice_detail"),
    "sales.salecreditnote": ("Credit note", "salecn_detail"), "inventory.stocktransfer": ("Stock transfer", "transfer_detail"),
    "jobwork.jobworkbill": ("Labour bill", "bill_detail"), "jobwork.jobworkchallan": ("Challan", "challan_detail"),
    "jobwork.receipt": ("Receipt", "receipt_detail"),
}


def source_link(voucher):
    """(label, number, url) of the document that made this voucher, or None for a hand-entered one (E9.1)."""
    from django.apps import apps
    from django.urls import reverse

    page = SOURCE_PAGES.get(voucher.source_type)
    if not page or not voucher.source_id:
        return None
    try:
        obj = apps.get_model(voucher.source_type).objects.filter(pk=voucher.source_id).first()
    except LookupError:
        return None
    if obj is None:
        return None
    return {"label": page[0], "number": getattr(obj, "number", None) or f"#{obj.pk}", "url": reverse(page[1], args=[obj.pk])}


class VoucherDetail(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "ledger.voucher"

    def _voucher(self, request, pk):
        return get_object_or_404(Voucher.objects.for_user(request.user).select_related("factory"), pk=pk)

    def get(self, request, pk):
        v = self._voucher(request, pk)
        lines = v.lines.select_related("ledger", "factory").prefetch_related("allocations")
        return render(request, "ledger/voucher_detail.html", {
            "v": v, "lines": lines, "reversal": v.reversals.first(), "source": source_link(v),
            "can_cancel": request.user.has_screen_perm("ledger.voucher", "cancel"),
        })

    def post(self, request, pk):
        v = self._voucher(request, pk)
        if not request.user.has_screen_perm("ledger.voucher", "cancel"):
            raise PermissionDenied
        try:
            reversal = reverse_voucher(v, user=request.user, reason=request.POST.get("reason", ""))
        except BusinessRuleError as exc:
            messages.error(request, str(exc))
            return redirect("voucher_detail", pk=pk)
        messages.success(request, f"{v.number} cancelled by {reversal.number}.")
        return redirect("voucher_detail", pk=reversal.pk)


# ---------------- manual vouchers: payment, receipt, contra, journal (E9.2, E9.3) ----------------

ENTRY_TITLES = {
    "payment": ("Money paid", "Money going out of cash or bank. Choose where it was paid from, then who or what it was paid to."),
    "receipt": ("Money received", "Money coming into cash or bank. Choose where it was received, then who or what it came from."),
    "contra": ("Contra voucher", "Money moved between your own cash and bank accounts, e.g. cash deposited in the bank."),
    "journal": ("Journal voucher", "Any other adjustment. Every row is a debit or a credit, and the two sides must be equal. "
                                   "Add GST or TDS ledgers as rows if the entry carries tax; nothing is added for you."),
}
ENTRY_ROWS = {"payment": 5, "receipt": 5, "journal": 6, "contra": 3}
POST_LABELS = {"payment": "Post payment", "receipt": "Post receipt", "contra": "Post contra voucher", "journal": "Post journal voucher"}


class VoucherEntry(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "ledger.voucher"
    screen_action = "create"

    def _context(self, request, vtype, rows=None, values=None):
        company = _company()
        groups = {}
        for l in Ledger.objects.filter(company=company, is_active=True).exclude(system_key="opening_difference").select_related("group"):
            groups.setdefault(l.group.name, []).append(l)
        title, intro = ENTRY_TITLES[vtype]
        values = values or {"date": timezone.localdate().isoformat()}
        # The Bill, Reference and Due columns are always in the page, so the form works without JavaScript. On Money
        # paid / received voucher_entry.js hides them while no row needs them.
        return {
            "vtype": vtype, "title": title, "intro": intro, "v": values, "post_label": POST_LABELS[vtype],
            "factory": request.factory,
            "ledger_groups": sorted(groups.items()), "cash_bank": cash_bank_ledgers(company).order_by("name"),
            "rows": rows or [{} for _ in range(ENTRY_ROWS[vtype])],
            "ref_types": [("on_account", "On account"), ("against", "Against bill"), ("new", "New bill"), ("advance", "Advance")],
        }

    def get(self, request, vtype):
        return render(request, "ledger/voucher_form.html", self._context(request, vtype, rows=self._prefill(request, vtype)))

    def _prefill(self, request, vtype):
        """'Receive payment' / 'Pay' buttons link here with ?ledger=&amount=&ref=&narration= to start a row already
        set to settle that bill. It only fills the form; nothing is posted until the user presses Post."""
        g = request.GET
        if vtype not in ("receipt", "payment") or not g.get("ledger", "").isdigit():
            return None
        if not Ledger.objects.filter(pk=int(g["ledger"]), company=_company(), is_active=True).exists():
            return None
        row = {"ledger": g["ledger"], "amount": g.get("amount", "")[:20], "ref_type": "against" if g.get("ref") else "on_account",
               "reference": g.get("ref", "")[:60], "narration": g.get("narration", "")[:200]}
        return [row] + [{} for _ in range(ENTRY_ROWS[vtype] - 1)]

    def post(self, request, vtype):
        p = request.POST
        company = _company()
        fields = ("ledger", "to_ledger", "amount", "debit", "credit", "ref_type", "reference", "due_date", "narration")
        cols = {f: p.getlist("row_" + f) for f in fields}
        count = max((len(v) for v in cols.values()), default=0)
        raw = [{f: (cols[f][i] if i < len(cols[f]) else "") for f in fields} for i in range(count)]
        values = {k: p.get(k, "") for k in ("date", "narration", "account", "from_account", "to_account", "amount", "vendor_invoice_no")}
        try:
            on_date = date.fromisoformat(values["date"]) if values["date"] else None
        except ValueError:
            on_date = None
        try:
            factory = require_active_factory(request)       # the factory chosen at login; the form never asks again
            voucher = post_manual_voucher(
                company=company, factory=factory, vtype=vtype, on_date=on_date, narration=values["narration"],
                header=values, rows=[Row(**r) for r in raw], user=request.user,
            )
        except BusinessRuleError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"{MANUAL_TYPES[vtype].label} {voucher.number} posted.")
            return redirect("voucher_detail", pk=voucher.pk)
        return render(request, "ledger/voucher_form.html", self._context(request, vtype, raw, values))


PARTY_TITLES = {
    "sales": ("Sales voucher", "A sale you book by hand against a customer. Choose a GST template if the sale carries GST; otherwise no tax is added."),
    "purchase": ("Purchase voucher", "A purchase or expense bill from a vendor. Choose a GST template and, if you deduct it, a TDS template; otherwise no tax is added."),
    "debit_note": ("Debit note", "Goods or value sent back to a vendor, settling their bill. A GST template reverses the GST claimed."),
    "credit_note": ("Credit note", "Goods or value taken back from a customer, settling their bill. A GST template reverses the GST charged."),
}


class PartyVoucherEntry(LoginRequiredMixin, ScreenPermissionMixin, View):
    """Sales, purchase, debit note and credit note by hand, with optional GST / TDS / TCS from a template (E9.2, E9.4)."""

    screen_code = "ledger.voucher"
    screen_action = "create"

    def _context(self, request, vtype, rows=None, values=None):
        from tax.models import TaxTemplate

        company = _company()
        groups = {}
        for l in Ledger.objects.filter(company=company, is_active=True).exclude(system_key="opening_difference").select_related("group"):
            groups.setdefault(l.group.name, []).append(l)
        receivable = vtype in ("sales", "credit_note")
        party_group = "Sundry Debtors" if receivable else "Sundry Creditors"
        title, intro = PARTY_TITLES[vtype]
        return {
            "vtype": vtype, "title": title, "intro": intro, "v": values or {"date": timezone.localdate().isoformat()},
            "factory": request.factory,
            "parties": [l for l in Ledger.objects.filter(company=company, is_active=True).select_related("group", "group__parent")
                        if l.group.name == party_group or (l.group.parent and l.group.parent.name == party_group)],
            "ledger_groups": sorted(groups.items()), "rows": rows or [{} for _ in range(4)],
            "gst_templates": TaxTemplate.objects.filter(kind="gst", is_active=True),
            "other_templates": TaxTemplate.objects.filter(kind="tds" if vtype == "purchase" else "tcs", is_active=True) if vtype in ("purchase", "sales") else [],
            "other_label": "TDS deducted" if vtype == "purchase" else "TCS collected",
            "ref_types": [("new", "New bill"), ("against", "Against bill"), ("advance", "Advance"), ("on_account", "On account")],
            "default_ref": "new" if vtype in ("purchase", "sales") else "against",
        }

    def get(self, request, vtype):
        if back := need_factory(request, "voucher_list"):
            return back
        return render(request, "ledger/party_voucher_form.html", self._context(request, vtype))

    def post(self, request, vtype):
        from tax.models import TaxTemplate

        p, company = request.POST, _company()
        if back := need_factory(request, "voucher_list"):
            return back
        factory = require_active_factory(request)
        names = ("ledger", "amount", "narration")
        cols = {n: p.getlist("row_" + n) for n in names}
        count = max((len(v) for v in cols.values()), default=0)
        raw = [{n: (cols[n][i] if i < len(cols[n]) else "") for n in names} for i in range(count)]
        values = {k: p.get(k, "") for k in ("date", "party", "reference", "ref_type", "due_date", "narration",
                                           "gst_template", "other_template", "override_reason")}
        for c in ("cgst", "sgst", "igst", "tax"):
            values[f"override_{c}"] = p.get(f"override_{c}", "")
        try:
            on_date = date.fromisoformat(values["date"]) if values["date"] else None
            due = date.fromisoformat(values["due_date"]) if values["due_date"] else None
            gst_t = TaxTemplate.objects.filter(pk=int(values["gst_template"])).first() if values["gst_template"].isdigit() else None
            other_t = TaxTemplate.objects.filter(pk=int(values["other_template"])).first() if values["other_template"].isdigit() else None
            overrides = {}
            for comp in ("cgst", "sgst", "igst"):
                if values[f"override_{comp}"].strip():
                    overrides[comp] = (parse_amount(values[f"override_{comp}"], comp.upper()), values["override_reason"])
            if values["override_tax"].strip() and other_t is not None:
                overrides[other_t.lines.first().component] = (parse_amount(values["override_tax"], "Tax"), values["override_reason"])
            voucher = post_party_voucher(
                company=company, factory=factory, vtype=vtype, on_date=on_date, party=values["party"], rows=[PartyRow(**r) for r in raw],
                user=request.user, narration=values["narration"], ref_type=values["ref_type"], reference=values["reference"],
                due_date=due, gst_template=gst_t, tax_template=other_t, overrides=overrides)
        except ValueError:
            messages.error(request, "Enter dates as YYYY-MM-DD.")
        except BusinessRuleError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"{voucher.get_voucher_type_display()} {voucher.number} posted.")
            return redirect("voucher_detail", pk=voucher.pk)
        return render(request, "ledger/party_voucher_form.html", self._context(request, vtype, raw, values))


class LedgerBills(LoginRequiredMixin, ScreenPermissionMixin, View):
    """Open bills of a bill-wise ledger, for the 'against bill' picker on the voucher screen."""
    screen_code = "ledger.voucher"

    def get(self, request, pk):
        ledger = get_object_or_404(Ledger, pk=pk, company=_company())
        data = outstanding_bills(ledger, user=request.user, factory=request.factory)
        bills = [{"reference": ref, "amount": str(abs(bal)), "side": "Dr" if bal > 0 else "Cr"}
                 for ref, bal in sorted(data["bills"].items())]
        pos = ledger_position(ledger, user=request.user)

        def side(v):
            return "Dr" if v > 0 else ("Cr" if v < 0 else "")
        return JsonResponse({
            "bill_wise": ledger.bill_wise, "bills": bills,
            "position": {
                "balance": str(abs(pos["balance"])), "balance_side": side(pos["balance"]),
                "outstanding": str(abs(pos["outstanding"])), "outstanding_side": side(pos["outstanding"]),
                "open_bills": pos["open_bills"],
                "advance": str(abs(pos["advance"])), "advance_side": side(pos["advance"]),
                "on_account": str(abs(pos["on_account"])), "on_account_side": side(pos["on_account"]),
            },
        })


# ---------------- opening balances (financial) ----------------

def _amount(text, label):
    text = (text or "").strip().replace(",", "")
    if not text:
        return ZERO
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise ValueError(f"{label}: '{text}' is not a number.")
    if value < 0 or value != value.quantize(Decimal("0.01")):
        raise ValueError(f"{label}: use a positive amount with at most two decimals.")
    return value.quantize(Decimal("0.01"))


class OpeningBalances(LoginRequiredMixin, ScreenPermissionMixin, View):
    """Opening balances for the books. Opening stock comes with the inventory step."""

    screen_code = "ledger.opening"

    def _context(self, request, rows=None, factory_id=None):
        company = _company()
        ledgers = Ledger.objects.filter(company=company, is_active=True).exclude(system_key="opening_difference")
        return {
            "company": company, "factory": request.factory,
            "ledgers": ledgers.select_related("group").order_by("group__name", "name"),
            "rows": rows or [{} for _ in range(6)], "factory_id": factory_id,
            "existing": Voucher.objects.for_user(request.user).filter(voucher_type="opening").select_related("factory"),
            "can_create": request.user.has_screen_perm("ledger.opening", "create"),
        }

    def get(self, request):
        if back := need_factory(request, "chart_of_accounts"):
            return back
        return render(request, "ledger/opening.html", self._context(request))

    def post(self, request):
        if not request.user.has_screen_perm("ledger.opening", "create"):
            raise PermissionDenied
        if back := need_factory(request, "chart_of_accounts"):
            return back
        company = _company()
        factory = require_active_factory(request)
        ledger_ids = request.POST.getlist("ledger")
        debits, credits = request.POST.getlist("debit"), request.POST.getlist("credit")
        refs, dues = request.POST.getlist("reference"), request.POST.getlist("due_date")
        rows, entries, errors = [], [], []
        for i, ledger_id in enumerate(ledger_ids):
            row = {"ledger": ledger_id, "debit": debits[i], "credit": credits[i],
                   "reference": refs[i], "due_date": dues[i]}
            rows.append(row)
            if not ledger_id and not (debits[i] or credits[i]):
                continue
            try:
                dr, cr = _amount(debits[i], f"Row {i + 1} debit"), _amount(credits[i], f"Row {i + 1} credit")
                if bool(dr) == bool(cr):
                    raise ValueError(f"Row {i + 1}: enter either a debit or a credit.")
                if not ledger_id:
                    raise ValueError(f"Row {i + 1}: choose a ledger.")
                due = date.fromisoformat(dues[i]) if dues[i] else None
                entries.append(OpeningEntry(
                    ledger=get_object_or_404(Ledger, pk=ledger_id, company=company),
                    debit=dr, credit=cr, reference=refs[i], due_date=due,
                ))
            except ValueError as exc:
                errors.append(str(exc))
        if not errors:
            try:
                voucher = post_opening_balances(company=company, factory=factory, entries=entries, user=request.user)
            except BusinessRuleError as exc:
                errors.append(str(exc))
            else:
                messages.success(request, f"Opening balances posted as {voucher.number}.")
                return redirect("voucher_detail", pk=voucher.pk)
        for e in errors:
            messages.error(request, e)
        return render(request, "ledger/opening.html", self._context(request, rows, factory.pk))


# ---------------- period locks and year end (E9.8, E9.9) ----------------

class PeriodLocks(LoginRequiredMixin, ScreenPermissionMixin, View):
    """Everything on or before the locked date is closed to posting. Locking is for the accountant; unlocking is the owner's."""

    screen_code = "core.period_lock"

    def get(self, request):
        from core.models import PeriodLock, PeriodLockLog

        company = _company()
        return render(request, "ledger/period_locks.html", {
            "locks": PeriodLock.objects.filter(company=company).select_related("factory").order_by("factory__code"),
            "log": PeriodLockLog.objects.filter(company=company).select_related("factory", "user")[:30],
            "factories": Factory.objects.for_user(request.user).filter(is_active=True),
            "can_lock": request.user.has_screen_perm("core.period_lock", "edit"),
            "can_unlock": request.user.has_screen_perm("core.period_lock", "approve")})

    def post(self, request):
        from core.services import periods

        company, p = _company(), request.POST
        try:
            factory = Factory.objects.filter(pk=int(p["factory"])).first() if p.get("factory", "").isdigit() else None
            if p.get("action") == "lock":
                periods.lock_period(user=request.user, company=company, upto=date.fromisoformat(p.get("upto", "")), factory=factory,
                                    reason=p.get("reason", "").strip() or "Period locked after filing")
                messages.success(request, "Period locked.")
            elif p.get("action") == "unlock":
                new_upto = date.fromisoformat(p["new_upto"]) if p.get("new_upto") else None
                periods.unlock_period(user=request.user, company=company, new_upto=new_upto, reason=p.get("reason", ""), factory=factory)
                messages.success(request, "Period unlocked.")
        except ValueError:
            messages.error(request, "Enter the date as YYYY-MM-DD.")
        except BusinessRuleError as exc:
            messages.error(request, str(exc))
        return redirect("period_locks")


class YearEnd(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "ledger.yearend"

    def get(self, request):
        from core.models import FinancialYear
        from core.services import yearend

        company = _company()
        years = [{"fy": fy, "checks": yearend.readiness(company, fy) if not fy.is_closed else []}
                 for fy in FinancialYear.objects.filter(company=company).order_by("start_date")]
        for y in years:
            y["ready"] = all(ok for ok, _ in y["checks"])
        latest_closed = max((y["fy"].start_date for y in years if y["fy"].is_closed), default=None)
        return render(request, "ledger/year_end.html", {
            "years": years, "latest_closed": latest_closed,
            "can_close": request.user.has_screen_perm("ledger.yearend", "edit"),
            "can_reopen": request.user.has_screen_perm("ledger.yearend", "approve")})

    def post(self, request):
        from core.models import FinancialYear
        from core.services import yearend

        company, p = _company(), request.POST
        fy = get_object_or_404(FinancialYear, pk=p.get("year"), company=company)
        try:
            if p.get("action") == "close":
                nxt = yearend.close_year(user=request.user, company=company, financial_year=fy, reason=p.get("reason", ""))
                messages.success(request, f"FY {fy.label} closed and locked. FY {nxt.label} is ready; balances carry forward on their own.")
            elif p.get("action") == "reopen":
                yearend.reopen_year(user=request.user, company=company, financial_year=fy, reason=p.get("reason", ""))
                messages.success(request, f"FY {fy.label} reopened. Post the adjustments, then close it again.")
        except BusinessRuleError as exc:
            messages.error(request, str(exc))
        return redirect("year_end")


# ---------------- trial balance ----------------

class TrialBalanceView(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "ledger.report"

    def get(self, request):
        factory = request.factory          # the session's active factory; None = all the user's factories
        as_of = timezone.localdate()          # "as of" is today unless another date is chosen
        if request.GET.get("as_of"):
            try:
                as_of = date.fromisoformat(request.GET["as_of"])
            except ValueError:
                messages.error(request, "Enter the date as YYYY-MM-DD.")
        tb = trial_balance(_company(), user=request.user, factory=factory, as_of=as_of)
        return render(request, "ledger/trial_balance.html", {
            "tb": tb, "factory": factory, "as_of": request.GET.get("as_of", ""),
        })
