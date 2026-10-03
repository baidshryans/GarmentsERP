from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from core.exceptions import BusinessRuleError
from core.models import Company, Factory
from core.scoping import ScreenPermissionMixin

from .forms import GroupForm, LedgerForm
from .models import AccountGroup, Ledger, Voucher, VoucherType
from .selectors import trial_balance
from .services.opening import OpeningEntry, post_opening_balances
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
        return render(request, "core/form.html", {"form": form, "title": "Account group"})

    def post(self, request, pk=None):
        form = GroupForm(request.POST, instance=self._obj(pk), company=_company())
        if form.is_valid():
            form.save()
            messages.success(request, "Group saved.")
            return redirect("chart_of_accounts")
        return render(request, "core/form.html", {"form": form, "title": "Account group"})


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
        return render(request, "core/form.html", {"form": form, "title": "Ledger"})

    def post(self, request, pk=None):
        form = LedgerForm(request.POST, instance=self._obj(pk), company=_company())
        if form.is_valid():
            form.save()
            messages.success(request, "Ledger saved. A ledger with entries can be deactivated but never deleted.")
            return redirect("chart_of_accounts")
        return render(request, "core/form.html", {"form": form, "title": "Ledger"})


# ---------------- vouchers (read, reverse) ----------------

class VoucherList(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "ledger.voucher"

    def get(self, request):
        qs = Voucher.objects.for_user(request.user).select_related("factory")
        factory = request.GET.get("factory")
        vtype = request.GET.get("type")
        status = request.GET.get("status")
        if factory:
            qs = qs.filter(factory_id=factory)
        if vtype:
            qs = qs.filter(voucher_type=vtype)
        if status:
            qs = qs.filter(status=status)
        return render(request, "ledger/voucher_list.html", {
            "vouchers": qs[:200], "factories": Factory.objects.for_user(request.user),
            "types": VoucherType.choices, "f": {"factory": factory, "type": vtype, "status": status},
        })


class VoucherDetail(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "ledger.voucher"

    def _voucher(self, request, pk):
        return get_object_or_404(Voucher.objects.for_user(request.user).select_related("factory"), pk=pk)

    def get(self, request, pk):
        v = self._voucher(request, pk)
        lines = v.lines.select_related("ledger", "factory").prefetch_related("allocations")
        return render(request, "ledger/voucher_detail.html", {
            "v": v, "lines": lines, "reversal": v.reversals.first(),
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
            "company": company, "factories": Factory.objects.for_user(request.user).filter(is_active=True),
            "ledgers": ledgers.select_related("group").order_by("group__name", "name"),
            "rows": rows or [{} for _ in range(6)], "factory_id": factory_id,
            "existing": Voucher.objects.for_user(request.user).filter(voucher_type="opening").select_related("factory"),
            "can_create": request.user.has_screen_perm("ledger.opening", "create"),
        }

    def get(self, request):
        return render(request, "ledger/opening.html", self._context(request))

    def post(self, request):
        if not request.user.has_screen_perm("ledger.opening", "create"):
            raise PermissionDenied
        company = _company()
        factory = get_object_or_404(Factory.objects.for_user(request.user), pk=request.POST.get("factory"))
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


# ---------------- trial balance ----------------

class TrialBalanceView(LoginRequiredMixin, ScreenPermissionMixin, View):
    screen_code = "ledger.report"

    def get(self, request):
        factories = Factory.objects.for_user(request.user)
        factory = None
        if request.GET.get("factory"):
            factory = get_object_or_404(factories, pk=request.GET["factory"])
        as_of = None
        if request.GET.get("as_of"):
            try:
                as_of = date.fromisoformat(request.GET["as_of"])
            except ValueError:
                messages.error(request, "Enter the date as YYYY-MM-DD.")
        tb = trial_balance(_company(), user=request.user, factory=factory, as_of=as_of)
        return render(request, "ledger/trial_balance.html", {
            "tb": tb, "factories": factories, "factory": factory, "as_of": request.GET.get("as_of", ""),
        })
