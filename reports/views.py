"""Accounting reports: ledger statement, day book, profit and loss, balance sheet, ageing (E9.5, ACC-04/06/07/19)."""
from datetime import date
from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from core.models import Company, Factory, FinancialYear
from core.scoping import ScreenPermissionMixin
from ledger.models import Ledger, VoucherType
from reports.export import xlsx_response
from reports.services import books

ZERO = Decimal("0.00")


def _company():
    return Company.objects.get(setup_complete=True)


def _year_start(company, today):
    fy = FinancialYear.objects.filter(company=company, start_date__lte=today, end_date__gte=today).first()
    return fy.start_date if fy else today.replace(month=4, day=1) if today.month >= 4 else today.replace(year=today.year - 1, month=4, day=1)


class ReportView(LoginRequiredMixin, ScreenPermissionMixin, View):
    """Common filters: factory (or all the user may see), a date range or an 'as of' date, and Excel export."""

    screen_code = "ledger.report"
    template_name = None
    needs_range = True

    def filters(self, request):
        company, today = _company(), timezone.localdate()
        g, problems = request.GET, []

        def day(key, default):
            if not g.get(key):
                return default
            try:
                return date.fromisoformat(g[key])
            except ValueError:
                problems.append(f"'{g[key]}' is not a date (use YYYY-MM-DD).")
                return default

        factories = Factory.objects.for_user(request.user)
        factory = factories.filter(pk=g["factory"]).first() if g.get("factory", "").isdigit() else None
        return {"company": company, "factories": factories, "factory": factory, "problems": problems, "today": today,
                "date_from": day("from", _year_start(company, today)), "date_to": day("to", today), "as_of": day("as_of", today)}

    def get(self, request, **kwargs):
        f = self.filters(request)
        ctx = self.build(request, f, **kwargs)
        ctx.update({k: f[k] for k in ("factories", "factory", "problems", "date_from", "date_to", "as_of")})
        if request.GET.get("format") == "xlsx" and not f["problems"]:
            return self.export(ctx)
        return render(request, self.template_name, ctx)


class LedgerStatement(ReportView):
    template_name = "reports/ledger_statement.html"

    def build(self, request, f, pk):
        ledger = get_object_or_404(Ledger.objects.select_related("group"), pk=pk, company=f["company"])
        st = books.ledger_statement(ledger, user=request.user, factory=f["factory"], date_from=f["date_from"], date_to=f["date_to"])
        return {"st": st, "ledger": ledger, "ledgers": Ledger.objects.filter(company=f["company"], is_active=True).order_by("name")}

    def export(self, ctx):
        st = ctx["st"]
        rows = [(r["date"], r["voucher"].number, r["type"], r["particulars"], r["debit"], r["credit"], r["balance"]) for r in st["rows"]]
        rows.insert(0, (ctx["date_from"], "", "Opening balance", "", "", "", st["opening"]))
        return xlsx_response(f"ledger-{st['ledger'].name}", st["ledger"].name, ("Date", "Voucher", "Type", "Particulars", "Debit", "Credit", "Balance (Dr +)"), rows,
                             notes=[f"{ctx['date_from']} to {ctx['date_to']}" + (f", factory {ctx['factory'].code}" if ctx["factory"] else ", all factories")])


class LedgerPicker(ReportView):
    """Pick any ledger and open its statement."""

    template_name = "reports/ledger_pick.html"

    def build(self, request, f):
        groups = {}
        for l in Ledger.objects.filter(company=f["company"], is_active=True).select_related("group").order_by("group__sort_order", "name"):
            groups.setdefault(l.group.name, []).append(l)
        return {"groups": list(groups.items())}


class LedgerBook(ReportView):
    """Tick any number of ledgers and see each one's entries with a running balance, one after another."""

    template_name = "reports/ledger_book.html"

    def build(self, request, f):
        groups, by_id = {}, {}
        for l in Ledger.objects.filter(company=f["company"], is_active=True).select_related("group").order_by("group__sort_order", "name"):
            groups.setdefault(l.group.name, []).append(l)
            by_id[l.pk] = l
        picked_ids = [int(x) for x in request.GET.getlist("ledger") if x.isdigit() and int(x) in by_id]
        picked = [by_id[i] for i in dict.fromkeys(picked_ids)]
        book = books.ledger_book(picked, user=request.user, factory=f["factory"], date_from=f["date_from"], date_to=f["date_to"]) if picked else None
        return {"groups": list(groups.items()), "picked_ids": {l.pk for l in picked}, "book": book, "asked": "ledger" in request.GET or "from" in request.GET}

    def export(self, ctx):
        rows = []
        for st in ctx["book"]["statements"]:
            rows.append((ctx["date_from"], st["ledger"].name, "", "Opening balance", "", "", st["opening"]))
            rows += [(r["date"], st["ledger"].name, r["voucher"].number, r["particulars"], r["debit"], r["credit"], r["balance"]) for r in st["rows"]]
            rows.append((ctx["date_to"], st["ledger"].name, "", "Closing balance", st["debit"], st["credit"], st["closing"]))
        return xlsx_response("ledger-book", "Ledger book", ("Date", "Ledger", "Voucher", "Particulars", "Debit", "Credit", "Balance (Dr +)"), rows,
                             notes=[f"{ctx['date_from']} to {ctx['date_to']}" + (f", factory {ctx['factory'].code}" if ctx["factory"] else ", all factories")])

    def get(self, request, **kwargs):
        if request.GET.get("format") == "xlsx" and not request.GET.getlist("ledger"):
            return redirect(request.path)
        return super().get(request, **kwargs)


class DayBook(ReportView):
    template_name = "reports/day_book.html"

    def build(self, request, f):
        vtype = request.GET.get("type") or None
        return {"book": books.day_book(f["company"], user=request.user, factory=f["factory"], date_from=f["date_from"],
                                       date_to=f["date_to"], voucher_type=vtype), "types": VoucherType.choices, "vtype": vtype}

    def export(self, ctx):
        rows = [(v.date, v.number, v.get_voucher_type_display(), v.factory.code, v.narration, v.total) for v in ctx["book"]["vouchers"]]
        return xlsx_response("day-book", "Day book", ("Date", "Voucher", "Type", "Factory", "Narration", "Amount"), rows,
                             notes=[f"{ctx['date_from']} to {ctx['date_to']}"])


class ProfitLoss(ReportView):
    template_name = "reports/profit_loss.html"

    def build(self, request, f):
        kw = dict(user=request.user, factory=f["factory"], date_from=f["date_from"], date_to=f["date_to"])
        compare = request.GET.get("compare") == "1"
        if compare:
            return {"cmp": books.compare_profit_and_loss(f["company"], **kw), "compare": True}
        return {"pl": books.profit_and_loss(f["company"], **kw), "compare": False}

    def export(self, ctx):
        rows = []
        if ctx["compare"]:
            for block in ctx["cmp"]["lines"]:
                rows.append((block["section"], "", ""))
                rows += [("   " + name, now, before) for name, now, before in block["rows"]]
            n, b = ctx["cmp"]["now"], ctx["cmp"]["before"]
            rows += [("Gross profit", n["gross_profit"], b["gross_profit"]), ("Net profit", n["net_profit"], b["net_profit"])]
            heads = ("", "This period", "Same days last year")
        else:
            pl = ctx["pl"]
            for label, key in (("Sales and direct income", "income"), ("Purchases and direct expenses", "expense")):
                rows.append((label, ""))
                rows += [("   " + r["ledger"], r["amount"]) for r in pl[key]]
            rows.append(("Gross profit", pl["gross_profit"]))
            for label, key in (("Indirect income", "other_income"), ("Indirect expenses", "other_expense")):
                rows.append((label, ""))
                rows += [("   " + r["ledger"], r["amount"]) for r in pl[key]]
            rows.append(("Net profit", pl["net_profit"]))
            heads = ("", "Amount")
        return xlsx_response("profit-and-loss", "Profit and loss", heads, rows, notes=[f"{ctx['date_from']} to {ctx['date_to']}"])


class BalanceSheet(ReportView):
    template_name = "reports/balance_sheet.html"

    def build(self, request, f):
        return {"bs": books.balance_sheet(f["company"], user=request.user, factory=f["factory"], as_of=f["as_of"])}

    def export(self, ctx):
        bs = ctx["bs"]
        rows = [("Liabilities", "")] + [("   " + r["ledger"], r["amount"]) for r in bs["liabilities"]]
        rows += [("   Profit of earlier years", bs["prior_profit"]), ("   Profit of this year", bs["current_profit"]),
                 ("Total liabilities", bs["liabilities_total"]), ("Assets", "")]
        rows += [("   " + r["ledger"], r["amount"]) for r in bs["assets"]] + [("Total assets", bs["assets_total"])]
        return xlsx_response("balance-sheet", "Balance sheet", ("", "Amount"), rows, notes=[f"As at {ctx['as_of']}"])


class Ageing(ReportView):
    template_name = "reports/ageing.html"

    def build(self, request, f, kind):
        if kind not in ("debtors", "creditors"):
            raise Http404("Unknown ageing report")
        return {"ag": books.ageing(f["company"], user=request.user, kind=kind, factory=f["factory"], as_of=f["as_of"]), "kind": kind}

    def export(self, ctx):
        ag = ctx["ag"]
        rows = [(p["ledger"].name, *[p["buckets"][b] for b in ag["buckets"]], p["total"], p["unadjusted"]) for p in ag["parties"]]
        rows.append(("Total", *[ag["totals"][b] for b in ag["buckets"]], ag["total"], ag["unadjusted"]))
        return xlsx_response(f"ageing-{ag['kind']}", "Receivables" if ag["kind"] == "debtors" else "Payables",
                             ("Party", *ag["buckets"], "Outstanding", "Advance / on account"), rows, notes=[f"As at {ctx['as_of']}, days past due"])


# ---------------------------------------------------------------- GST and TDS returns (E9.10)

class TaxReportView(ReportView):
    screen_code = "tax.report"

    def build(self, request, f, **kw):
        from tax import services as tax_services

        ctx = self.data(request, f)
        ctx["gst_on"] = tax_services.gst_enabled(f["company"], f["date_to"])
        ctx["tds_on"] = tax_services.tds_enabled(f["company"], f["date_to"])
        return ctx


class Gstr1(TaxReportView):
    template_name = "reports/gstr1.html"

    def data(self, request, f):
        from reports.services import gst

        return {"r": gst.gstr1(f["company"], user=request.user, factory=f["factory"], date_from=f["date_from"], date_to=f["date_to"])}

    def export(self, ctx):
        r = ctx["r"]
        rows = [("B2B", x["gstin"], x["invoice"].customer.name, x["invoice"].number, x["invoice"].date, x["invoice"].place_of_supply,
                 x["rate"], x["taxable"], x["igst"], x["cgst"], x["sgst"]) for x in r["b2b"]]
        rows += [("B2C", "", "", "", "", x["place"], x["rate"], x["taxable"], x["igst"], x["cgst"], x["sgst"]) for x in r["b2c"]]
        rows += [("Credit note", x["gstin"], x["note"].customer.name, x["note"].number, x["note"].date, x["note"].invoice.place_of_supply,
                  "", -x["taxable"], -x["igst"], -x["cgst"], -x["sgst"]) for x in r["cdn"]]
        rows += [("HSN " + x["hsn"], "", "", "", "", "", x["rate"], x["taxable"], x["igst"], x["cgst"], x["sgst"]) for x in r["hsn"]]
        return xlsx_response("gstr1", "GSTR-1 data", ("Table", "GSTIN", "Party", "Document", "Date", "Place of supply", "Rate %", "Taxable",
                                                      "IGST", "CGST", "SGST"), rows, notes=[f"{ctx['date_from']} to {ctx['date_to']}"])


class Gstr3b(TaxReportView):
    template_name = "reports/gstr3b.html"

    def data(self, request, f):
        from reports.services import gst

        return {"r": gst.gstr3b(f["company"], user=request.user, factory=f["factory"], date_from=f["date_from"], date_to=f["date_to"])}

    def export(self, ctx):
        r = ctx["r"]
        rows = [("Outward taxable supplies (sales)", r["taxable_outward"], "", "", ""),
                ("Output tax", r["output"]["igst"], r["output"]["cgst"], r["output"]["sgst"], r["output_total"]),
                ("Reverse charge liability", r["rcm"]["igst"], r["rcm"]["cgst"], r["rcm"]["sgst"], r["rcm_total"]),
                ("Input tax credit", r["itc"]["igst"], r["itc"]["cgst"], r["itc"]["sgst"], r["itc_total"]),
                ("Tax payable (before set-off between heads)", r["payable"]["igst"], r["payable"]["cgst"], r["payable"]["sgst"], r["payable_total"])]
        return xlsx_response("gstr3b", "GSTR-3B summary", ("", "IGST", "CGST", "SGST", "Total"), rows, notes=[f"{ctx['date_from']} to {ctx['date_to']}"])


class TaxRegister(TaxReportView):
    template_name = "reports/tax_register.html"

    def data(self, request, f):
        from reports.services import gst

        kind = request.GET.get("kind") if request.GET.get("kind") in ("gst", "tds", "tcs") else "gst"
        return {"r": gst.tax_register(f["company"], user=request.user, factory=f["factory"], date_from=f["date_from"], date_to=f["date_to"], kind=kind),
                "kind": kind}

    def export(self, ctx):
        r = ctx["r"]
        rows = [(x["date"], x["voucher"].number, x["voucher"].get_voucher_type_display(), x["party"], x["ledger"], x["factory"], x["debit"], x["credit"])
                for x in r["rows"]]
        return xlsx_response(f"tax-register-{ctx['kind']}", f"{ctx['kind'].upper()} register", ("Date", "Voucher", "Type", "Party", "Ledger", "Factory", "Debit", "Credit"),
                             rows, notes=[f"{ctx['date_from']} to {ctx['date_to']}"])


# ---------------------------------------------------------------- operating reports (E10.1, E10.2)

class SalesReport(ReportView):
    screen_code = "sales.invoice"
    template_name = "reports/sales_report.html"

    def build(self, request, f):
        from reports.services import standard

        by = request.GET.get("by", "customer")
        r = standard.sales_report(user=request.user, factory=f["factory"], date_from=f["date_from"], date_to=f["date_to"], by=by)
        return {"r": r, "by": r["by"], "views": standard.SALES_VIEWS}

    def export(self, ctx):
        r = ctx["r"]
        rows = [(x["key"], x["pieces"], x["value"], x["gst"], x["returned_pieces"], x["returned_value"], x["net_pieces"], x["net_value"]) for x in r["rows"]]
        t = r["total"]
        rows.append(("Total", t["pieces"], t["value"], t["gst"], t["returned_pieces"], t["returned_value"], t["net_pieces"], t["net_value"]))
        return xlsx_response(f"sales-by-{r['by']}", "Sales", (r["by"].title(), "Pieces", "Value", "GST", "Returned pieces", "Returned value", "Net pieces", "Net value"),
                             rows, notes=[f"{ctx['date_from']} to {ctx['date_to']}"])


class PurchaseReport(ReportView):
    screen_code = "purchases.invoice"
    template_name = "reports/purchase_report.html"

    def build(self, request, f):
        from reports.services import standard

        by = "month" if request.GET.get("by") == "month" else "vendor"
        r = standard.purchase_report(user=request.user, factory=f["factory"], date_from=f["date_from"], date_to=f["date_to"], by=by)
        return {"r": r, "by": by}

    def export(self, ctx):
        r = ctx["r"]
        rows = [(x["key"], x["bills"], x["value"], x["gst"], x["payable"], x["variances"]) for x in r["rows"]]
        t = r["total"]
        rows.append(("Total", t["bills"], t["value"], t["gst"], t["payable"], t["variances"]))
        return xlsx_response("purchases", "Purchases", (r["by"].title(), "Bills", "Value", "GST", "Payable", "Rate differences"), rows,
                             notes=[f"{ctx['date_from']} to {ctx['date_to']}"])


class FinishedStock(ReportView):
    screen_code = "inventory.stock"
    template_name = "reports/finished_stock.html"

    def build(self, request, f):
        from reports.services import standard

        try:
            days = max(1, int(request.GET.get("slow", 60)))
        except ValueError:
            days = 60
        return {"r": standard.finished_stock(user=request.user, factory=f["factory"], today=f["today"], slow_days=days)}

    def export(self, ctx):
        r = ctx["r"]
        rows = [(str(x["sku"]), x["qty"], x["value"], x["last_in"], x["last_out"], x["age"], "Slow" if x["slow"] else "") for x in r["rows"]]
        return xlsx_response("finished-stock", "Finished stock", ("SKU", "Pieces", "Value", "Last in", "Last sold", "Days in stock", "Slow-moving"), rows,
                             notes=[f"Slow-moving: not sold in {r['slow_days']} days"])
