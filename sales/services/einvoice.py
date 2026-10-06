"""E-invoice (IRN and QR) and e-way bill (E4.5), behind an interface until a GST suvidha provider (GSP) is chosen.

The invoice-side logic (who may send, what is stored, how a failure is shown) is final. Only `EInvoiceProvider`
changes when a GSP is picked: write a class with the same three methods and name it in settings as
SALES_EINVOICE_PROVIDER = "dotted.path.to.Class". Until then the stub makes up a plausible IRN so screens and
printing can be built and tested; it never talks to a portal.
"""
import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.module_loading import import_string

from core.exceptions import BusinessRuleError
from core.scoping import assert_factory_access
from sales.models import SaleInvoice
from sales.services.common import settings_for
from tax import services as tax_services


class EInvoiceError(Exception):
    """The portal (or the provider) refused the request. The message is shown to the user as received."""


@dataclass
class IrnResult:
    irn: str
    ack_no: str
    ack_date: datetime
    qr_text: str


@dataclass
class EwayResult:
    number: str
    valid_until: date


class EInvoiceProvider:
    """What a GSP integration must offer."""

    def generate_irn(self, payload: dict) -> IrnResult:
        raise NotImplementedError

    def generate_eway(self, payload: dict, *, vehicle_no: str, transporter_gstin: str, distance_km: int) -> EwayResult:
        raise NotImplementedError

    def cancel_irn(self, irn: str, reason: str) -> None:
        raise NotImplementedError


class StubProvider(EInvoiceProvider):
    """Deterministic fake: the IRN is a SHA-256 of seller GSTIN, document number, year and type, like the real one."""

    def generate_irn(self, payload):
        doc = payload["DocDtls"]
        irn = hashlib.sha256(f"{payload['SellerDtls']['Gstin']}{doc['No']}{doc['Dt'][-4:]}INV".encode()).hexdigest()
        ack_no = str(int(irn[:12], 16) % 10 ** 15).zfill(15)
        qr = f"IRN:{irn}|ACK:{ack_no}|DOC:{doc['No']}|VAL:{payload['ValDtls']['TotInvVal']}"
        return IrnResult(irn=irn, ack_no=ack_no, ack_date=timezone.now(), qr_text=qr)

    def generate_eway(self, payload, *, vehicle_no, transporter_gstin, distance_km):
        number = str(int(hashlib.sha256(payload["DocDtls"]["No"].encode()).hexdigest()[:11], 16) % 10 ** 12).zfill(12)
        return EwayResult(number=number, valid_until=timezone.localdate() + timedelta(days=max(1, (distance_km or 100) // 200 + 1)))

    def cancel_irn(self, irn, reason):
        return None


def get_provider() -> EInvoiceProvider:
    path = getattr(settings, "SALES_EINVOICE_PROVIDER", "")
    return import_string(path)() if path else StubProvider()


# ---------------------------------------------------------------- the payload (NIC e-invoice schema, the parts we hold)

def _q(value):
    return float(Decimal(value).quantize(Decimal("0.01")))


def build_payload(invoice) -> dict:
    inv = SaleInvoice.objects.select_related("factory", "customer", "company").get(pk=invoice.pk)
    seller_gstin = inv.factory.gstin or tax_services.gst_registration(inv.company, inv.date, inv.factory)
    cust = inv.customer
    billing = cust.addresses.filter(kind="billing").first()
    items = []
    for n, l in enumerate(inv.lines.select_related("sku__style"), start=1):
        by = {t.component: t for t in l.taxes.all()}
        gross = l.qty * l.rate
        items.append({
            "SlNo": str(n), "PrdDesc": l.sku.style.name, "IsServc": "N", "HsnCd": l.hsn, "Qty": float(l.qty), "Unit": "PCS",
            "UnitPrice": _q(l.rate), "TotAmt": _q(gross), "Discount": _q(gross - l.amount), "AssAmt": _q(l.amount),
            "GstRt": float(l.gst_rate), "CgstAmt": _q(by["cgst"].amount) if "cgst" in by else 0.0,
            "SgstAmt": _q(by["sgst"].amount) if "sgst" in by else 0.0, "IgstAmt": _q(by["igst"].amount) if "igst" in by else 0.0,
            "TotItemVal": _q(l.amount + l.tax_amount),
        })
    gst = {c: sum((t.amount for t in inv.tax_lines.all() if t.component == c), Decimal("0")) for c in ("cgst", "sgst", "igst")}
    return {
        "Version": "1.1",
        "TranDtls": {"TaxSch": "GST", "SupTyp": "B2B", "RegRev": "N"},
        "DocDtls": {"Typ": "INV", "No": inv.number, "Dt": inv.date.strftime("%d/%m/%Y")},
        "SellerDtls": {"Gstin": seller_gstin, "LglNm": inv.company.name, "Addr1": inv.factory.address or inv.factory.name,
                       "Loc": inv.factory.city or "", "Stcd": inv.factory.state_code},
        "BuyerDtls": {"Gstin": cust.gstin, "LglNm": cust.name, "Pos": inv.place_of_supply, "Stcd": cust.state_code,
                      "Addr1": billing.line1 if billing else cust.name, "Loc": billing.city if billing else "",
                      "Pin": billing.pincode if billing else ""},
        "ItemList": items,
        "ValDtls": {"AssVal": _q(inv.subtotal), "CgstVal": _q(gst["cgst"]), "SgstVal": _q(gst["sgst"]), "IgstVal": _q(gst["igst"]),
                    "RndOffAmt": _q(inv.round_off), "TotInvVal": _q(inv.total)},
    }


# ---------------------------------------------------------------- actions

def is_available(invoice) -> bool:
    """The e-invoice buttons show only for a posted, taxed, business-to-business invoice of a registered company
    that has switched e-invoicing on."""
    return (settings_for(invoice.company).einvoice_enabled
            and tax_services.gst_enabled(invoice.company, invoice.date, invoice.factory)
            and invoice.status == SaleInvoice.Status.POSTED and invoice.tax_mode != SaleInvoice.TaxMode.NONE
            and bool(invoice.customer.gstin))


@transaction.atomic
def submit(invoice, *, user, vehicle_no="", distance_km=0) -> SaleInvoice:
    """One click: IRN and QR, plus the e-way bill when the value needs one or a vehicle is given.

    A portal failure does not raise: it is stored on the invoice so the screen shows the portal's own message."""
    inv = SaleInvoice.objects.select_related("factory", "customer", "company", "transporter").get(pk=invoice.pk)
    assert_factory_access(user, inv.factory)
    if not is_available(inv):
        raise BusinessRuleError("E-invoicing is not available for this bill (it needs a posted bill with GST, a buyer GSTIN "
                                "and e-invoicing switched on in the sales settings).")
    if inv.einvoice_status == SaleInvoice.EInvoice.GENERATED and inv.eway_bill_no:
        raise BusinessRuleError("The e-invoice and e-way bill have already been generated.")
    setting = settings_for(inv.company)
    vehicle_no = (vehicle_no or inv.vehicle_no).strip().upper()
    transporter_gstin = inv.transporter.gstin if inv.transporter_id else ""
    needs_eway = inv.total >= setting.eway_threshold
    if needs_eway and not vehicle_no and not transporter_gstin:
        raise BusinessRuleError("This bill needs an e-way bill: enter the vehicle number, or pick a transporter with a GSTIN.")
    provider, payload = get_provider(), build_payload(inv)
    try:
        if inv.einvoice_status != SaleInvoice.EInvoice.GENERATED:
            res = provider.generate_irn(payload)
            inv.irn, inv.ack_no, inv.ack_date, inv.qr_text = res.irn, res.ack_no, res.ack_date, res.qr_text
            inv.einvoice_status = SaleInvoice.EInvoice.GENERATED
        if needs_eway or vehicle_no:
            eway = provider.generate_eway(payload, vehicle_no=vehicle_no, transporter_gstin=transporter_gstin, distance_km=distance_km)
            inv.eway_bill_no, inv.eway_valid_until = eway.number, eway.valid_until
        inv.vehicle_no = vehicle_no or inv.vehicle_no
        inv.einvoice_error = ""
    except EInvoiceError as exc:
        inv.einvoice_status = inv.einvoice_status if inv.irn else SaleInvoice.EInvoice.FAILED
        inv.einvoice_error = str(exc)[:500]
    inv.save()
    return inv


@transaction.atomic
def cancel(invoice, *, user, reason) -> SaleInvoice:
    """Cancel the IRN (needed before an invoice can be cancelled in the books)."""
    inv = SaleInvoice.objects.select_related("factory").get(pk=invoice.pk)
    assert_factory_access(user, inv.factory)
    if inv.einvoice_status != SaleInvoice.EInvoice.GENERATED:
        raise BusinessRuleError("There is no IRN to cancel.")
    if not reason.strip():
        raise BusinessRuleError("Give a reason to cancel the e-invoice.")
    try:
        get_provider().cancel_irn(inv.irn, reason.strip())
    except EInvoiceError as exc:
        raise BusinessRuleError(f"The portal refused the cancellation: {exc}")
    inv.einvoice_status = SaleInvoice.EInvoice.NONE
    inv.irn = inv.ack_no = inv.qr_text = inv.eway_bill_no = ""
    inv.ack_date = inv.eway_valid_until = None
    inv.einvoice_error = ""
    inv.save()
    return inv
