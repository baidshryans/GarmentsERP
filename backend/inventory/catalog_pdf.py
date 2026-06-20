"""
Catalog / quotation PDF generation using reportlab.

weasyprint (the usual HTML->PDF route) needs native GTK libraries that aren't
available on this Windows host, so we build the documents directly with
reportlab.platypus instead.

Three layouts, each driven by the same `rows` produced by the catalog view:
  - summary   : image grid, a few key specs + price per design
  - detailed  : per-design component breakdown (gold / stones / making + totals)
  - quotation : one tabular row per design (landscape)

Each row is a dict:
  {
    'design_no', 'item_name', 'gw', 'nw', 'in_stock_count',
    'image_path' (abs path or None),
    'price': <compute_design_price() dict>,
  }
`meta` carries header info: {'title', 'tier_label', 'date'}.
"""

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image,
)

ACCENT = colors.HexColor("#7c3aed")
MUTED = colors.HexColor("#6b7280")
LINE = colors.HexColor("#e5e7eb")


def _rs(v):
    return "Rs " + format(int(round(float(v or 0))), ",d")


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("Cap", parent=ss["Normal"], fontSize=7, textColor=MUTED))
    ss.add(ParagraphStyle("DesignNo", parent=ss["Normal"], fontSize=9, leading=11, fontName="Helvetica-Bold"))
    ss.add(ParagraphStyle("Price", parent=ss["Normal"], fontSize=10, fontName="Helvetica-Bold"))
    ss.add(ParagraphStyle("H", parent=ss["Title"], fontSize=16, textColor=ACCENT, spaceAfter=2))
    ss.add(ParagraphStyle("Sub", parent=ss["Normal"], fontSize=8, textColor=MUTED, spaceAfter=8))
    ss.add(ParagraphStyle("CellName", parent=ss["Normal"], fontSize=8, leading=10))
    return ss


def _img(path, w, h):
    if not path:
        return Paragraph("", getSampleStyleSheet()["Normal"])
    try:
        return Image(path, width=w, height=h, kind="proportional")
    except Exception:
        return Paragraph("", getSampleStyleSheet()["Normal"])


def _header(ss, meta):
    return [
        Paragraph(meta.get("title", "Catalog"), ss["H"]),
        Paragraph(f"{meta.get('tier_label', 'Retail')} &nbsp;·&nbsp; {meta.get('date', '')} &nbsp;·&nbsp; {meta.get('count', 0)} designs", ss["Sub"]),
    ]


def _doc(buf, pagesize):
    return SimpleDocTemplate(
        buf, pagesize=pagesize,
        leftMargin=12 * mm, rightMargin=12 * mm, topMargin=12 * mm, bottomMargin=12 * mm,
        title="Catalog",
    )


# ── Summary: image grid ─────────────────────────────────────────────────────────
def build_summary_pdf(rows, meta):
    ss = _styles()
    buf = io.BytesIO()
    doc = _doc(buf, A4)
    story = _header(ss, meta)

    cols = 3
    cells = []
    for r in rows:
        p = r["price"]
        inner = Table([
            [_img(r.get("image_path"), 42 * mm, 42 * mm)],
            [Paragraph(r["design_no"], ss["DesignNo"])],
            [Paragraph(f"{r.get('item_name') or ''}", ss["Cap"])],
            [Paragraph(f"{r['nw']} g · {p.get('gold_purity') or '-'}", ss["Cap"])],
            [Paragraph(_rs(p.get("total_price")), ss["Price"])],
        ], colWidths=[44 * mm])
        inner.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 1), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ]))
        cells.append(inner)

    while len(cells) % cols != 0:
        cells.append("")
    grid = [cells[i:i + cols] for i in range(0, len(cells), cols)]
    t = Table(grid, colWidths=[60 * mm] * cols)
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(t)
    doc.build(story)
    return buf.getvalue()


# ── Detailed: per-design component breakdown ────────────────────────────────────
def build_detailed_pdf(rows, meta):
    ss = _styles()
    buf = io.BytesIO()
    doc = _doc(buf, A4)
    story = _header(ss, meta)

    for r in rows:
        p = r["price"]
        head = Table([[
            _img(r.get("image_path"), 30 * mm, 30 * mm),
            [
                Paragraph(r["design_no"], ss["DesignNo"]),
                Paragraph(f"{r.get('item_name') or ''} · {r['nw']} g · {p.get('gold_purity') or '-'}", ss["Cap"]),
            ],
        ]], colWidths=[32 * mm, 150 * mm])
        head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(head)

        data = [["Component", "Pcs", "Ct", "Amount"]]
        for c in p.get("component_lines", []):
            data.append([
                c.get("name", ""),
                str(c.get("pcs", "") or ""),
                (str(c.get("ct")) if c.get("ct") else ""),
                _rs(c.get("amount")),
            ])
        data.append(["", "", "Taxable", _rs(p.get("taxable"))])
        data.append(["", "", f"GST {p.get('gst_pct', 0)}%", _rs(p.get("gst"))])
        data.append(["", "", "Total", _rs(p.get("total_price"))])

        tbl = Table(data, colWidths=[95 * mm, 20 * mm, 30 * mm, 37 * mm])
        tbl.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, LINE),
            ("LINEABOVE", (2, -3), (-1, -3), 0.5, LINE),
            ("FONTNAME", (2, -1), (-1, -1), "Helvetica-Bold"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 8 * mm))
    doc.build(story)
    return buf.getvalue()


# ── Quotation: tabular (landscape) ──────────────────────────────────────────────
def build_quotation_pdf(rows, meta):
    ss = _styles()
    buf = io.BytesIO()
    doc = _doc(buf, landscape(A4))
    story = _header(ss, meta)

    head = ["#", "Image", "Design", "Item", "Purity", "GW", "NW", "Gold", "Stones", "Making", "GST", "Total"]
    data = [head]
    for i, r in enumerate(rows, 1):
        p = r["price"]
        data.append([
            str(i),
            _img(r.get("image_path"), 16 * mm, 16 * mm),
            r["design_no"],
            Paragraph(r.get("item_name") or "", ss["CellName"]),
            p.get("gold_purity") or "-",
            str(r["gw"]), str(r["nw"]),
            _rs(p.get("gold_value")), _rs(p.get("stone_total")),
            _rs(p.get("making_value")), _rs(p.get("gst")), _rs(p.get("total_price")),
        ])

    widths = [8, 20, 24, 40, 16, 16, 16, 28, 28, 26, 22, 30]
    tbl = Table(data, colWidths=[w * mm for w in widths], repeatRows=1)
    tbl.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (5, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#faf5ff")]),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(tbl)
    doc.build(story)
    return buf.getvalue()


BUILDERS = {
    "summary": build_summary_pdf,
    "detailed": build_detailed_pdf,
    "quotation": build_quotation_pdf,
}


def _empty_pdf(meta):
    ss = _styles()
    buf = io.BytesIO()
    doc = _doc(buf, A4)
    story = _header(ss, meta)
    story.append(Paragraph("No designs match the current filters.", ss["Sub"]))
    doc.build(story)
    return buf.getvalue()


def build_catalog_pdf(fmt, rows, meta):
    if not rows:
        return _empty_pdf(meta)
    return BUILDERS.get(fmt, build_summary_pdf)(rows, meta)
