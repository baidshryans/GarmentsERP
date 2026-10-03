"""Bundle tags: a QR code per bundle (BAR-02, PRD-06), as inline SVG for A4 and thermal labels, and as ZPL for Zebra printers."""
import re

import segno

PREFIX = "GE1:"


def scan_text(bundle) -> str:
    """What the QR holds: a short token with a prefix so scanners can tell our tags from any other QR."""
    return f"{PREFIX}{bundle.qr_token}"


def parse_scan(text: str) -> str:
    """The token from whatever a scanner typed (with or without the prefix, any stray whitespace)."""
    text = (text or "").strip()
    return text[len(PREFIX):] if text.startswith(PREFIX) else text


def qr_svg(bundle, scale: int = 3) -> str:
    code = segno.make(scan_text(bundle), error="m", micro=False)
    return code.svg_inline(scale=scale, border=1, dark="#000", light="#fff", omitsize=False)


def _zpl_text(value) -> str:
    """ZPL treats ^ and ~ as commands, so they are removed from printed text."""
    return re.sub(r"[\^~\\]", " ", str(value))


def zpl_label(bundle, *, width_mm=100, height_mm=50, dpi=203) -> str:
    """One ZPL label: lot, style, colour, size, quantity, bundle number and the QR code."""
    dots = lambda mm: int(round(mm * dpi / 25.4))
    lot, sku = bundle.lot, bundle.sku
    qr_mag = 5 if width_mm >= 90 else 3
    lines = [
        "^XA", f"^PW{dots(width_mm)}", f"^LL{dots(height_mm)}", "^CI28",
        f"^FO{dots(3)},{dots(3)}^BQN,2,{qr_mag}^FDQA,{scan_text(bundle)}^FS",
        f"^FO{dots(width_mm * 0.45)},{dots(3)}^A0N,{dots(6)},{dots(6)}^FD{_zpl_text(lot.style.style_no)}^FS",
        f"^FO{dots(width_mm * 0.45)},{dots(11)}^A0N,{dots(4.5)},{dots(4.5)}^FD{_zpl_text(sku.colour)} / {_zpl_text(sku.size)}^FS",
        f"^FO{dots(width_mm * 0.45)},{dots(18)}^A0N,{dots(4.5)},{dots(4.5)}^FDQty {bundle.original_qty}   {_zpl_text(bundle.bundle_no)}^FS",
        f"^FO{dots(width_mm * 0.45)},{dots(25)}^A0N,{dots(3.5)},{dots(3.5)}^FD{_zpl_text(lot.lot_no)}^FS",
        "^XZ",
    ]
    return "\n".join(lines)


def zpl_for(bundles, **kw) -> str:
    return "\n".join(zpl_label(b, **kw) for b in bundles) + "\n"
