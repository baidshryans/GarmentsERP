"""Styles and SKUs (E2.1)."""
from io import BytesIO

from django.core.files.base import ContentFile
from django.db import transaction
from PIL import Image

from core.exceptions import BusinessRuleError
from masters.models import SKU, Style, StyleColour, StyleSize
from masters.services.codes import next_barcode

THUMB_SIZE = (320, 320)


def pieces_per_box(style, company) -> int:
    """Pieces packed in one box for a style: its own setting, else the company's. 0 = boxes are not counted."""
    if style.pieces_per_box:
        return style.pieces_per_box
    return company.pieces_per_box if company is not None else 0


@transaction.atomic
def sync_variants(style, *, colours, sizes, company):
    """Make the style's colours and sizes exactly these, and make sure every combination has a SKU.

    Only missing SKUs are created. SKUs are never deleted: a removed colour or size just
    deactivates its SKUs, and re-adding it reactivates them (stock history stays intact).
    """
    colours, sizes = list(colours), list(sizes)
    if not colours or not sizes:
        raise BusinessRuleError("A style needs at least one colour and one size.")

    keep_c = {c.pk for c in colours}
    keep_s = {s.pk for s in sizes}
    style.style_colours.exclude(colour_id__in=keep_c).delete()
    style.style_sizes.exclude(size_id__in=keep_s).delete()
    for c in colours:
        StyleColour.objects.get_or_create(style=style, colour=c)
    for s in sizes:
        StyleSize.objects.get_or_create(style=style, size=s)

    existing = {(k.colour_id, k.size_id): k for k in SKU.objects.filter(style=style)}
    for c in colours:
        for s in sizes:
            sku = existing.get((c.pk, s.pk))
            if sku is None:
                SKU.objects.create(style=style, colour=c, size=s, barcode=next_barcode(company))
            elif not sku.is_active:
                sku.is_active = True
                sku.save(update_fields=["is_active"])
    for (cid, sid), sku in existing.items():
        if (cid not in keep_c or sid not in keep_s) and sku.is_active:
            sku.is_active = False
            sku.save(update_fields=["is_active"])


@transaction.atomic
def create_style(*, company, style_no, product, name, colours, sizes, **extra) -> Style:
    style = Style(style_no=style_no.strip().upper(), product=product, name=name, **extra)
    style.full_clean()
    style.save()
    sync_variants(style, colours=colours, sizes=sizes, company=company)
    if style.image:
        make_thumbnail(style)
    return style


def make_thumbnail(style):
    """Keep the original on disk and store a small compressed copy for lists and apps (BAR-08)."""
    with style.image.open("rb") as fh:
        img = Image.open(fh)
        img.load()
    img = img.convert("RGB")
    img.thumbnail(THUMB_SIZE)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=72, optimize=True)
    style.thumbnail.save(f"{style.style_no}.jpg", ContentFile(buf.getvalue()), save=False)
    style.save(update_fields=["thumbnail"])
