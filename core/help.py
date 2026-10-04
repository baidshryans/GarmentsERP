"""The in-app help: renders docs/SETUP_GUIDE.md (setup guide and user guide) as one searchable page.

The Markdown file is the single source. It is re-rendered only when the file changes, and raw HTML in it is
never passed through, so what the page shows is exactly the guide's text, tables and headings.
"""
import re
from pathlib import Path

from django.conf import settings
from markdown_it import MarkdownIt

GUIDE_PATH = Path(settings.BASE_DIR) / "docs" / "SETUP_GUIDE.md"
_cache = {}

# URL prefix -> guide section, longest prefix first. The help icon opens the guide at the section for the current screen.
SECTION_FOR_PATH = [
    ("/setup/", 2), ("/factories/", 3), ("/users/", 3), ("/roles/", 3), ("/tax/", 4), ("/settings/inventory", 5),
    ("/settings/sales", 26), ("/accounts/chart", 6), ("/accounts/ledgers/", 6), ("/accounts/opening", 13),
    ("/inventory/opening", 13), ("/import/", 14), ("/masters/routes", 8), ("/masters/parties", 9),
    ("/masters/styles", 10), ("/masters/pricelist", 12), ("/masters/hsn", 4), ("/masters/", 7),
    ("/jobwork/rates", 11), ("/jobwork/bills", 25), ("/jobwork/", 23), ("/production/orders", 20),
    ("/production/lots/", 21), ("/production/move", 23), ("/production/", 24),
    ("/sales/", 26), ("/accounts/vouchers/receipt", 27), ("/accounts/vouchers/payment", 25),
    ("/accounts/vouchers/", 28), ("/accounts/ageing", 29), ("/accounts/", 29), ("/reports/", 29),
]


def _plain(text):
    return re.sub(r"[`*_]", "", text).strip()


def _slug(title, taken):
    num = re.match(r"(\d+)\.\s", title)
    if num:
        base = f"s{num.group(1)}"
    else:
        part = re.match(r"Part ([A-Z])\b", title)
        base = f"part-{part.group(1).lower()}" if part else re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "section"
    slug, n = base, 2
    while slug in taken:
        slug, n = f"{base}-{n}", n + 1
    taken.add(slug)
    return slug


def render_guide():
    """{"html", "toc": [{level, title, id}], "sections": set of ids}; cached until the file changes."""
    stamp = GUIDE_PATH.stat().st_mtime
    if _cache.get("stamp") == stamp:
        return _cache["data"]
    md = MarkdownIt("commonmark", {"html": False}).enable("table")
    tokens = md.parse(GUIDE_PATH.read_text(encoding="utf-8"))
    toc, taken = [], set()
    for i, tok in enumerate(tokens):
        if tok.type == "heading_open" and tok.tag in ("h1", "h2", "h3"):
            title = _plain(tokens[i + 1].content)
            slug = _slug(title, taken)
            tok.attrSet("id", slug)
            toc.append({"level": int(tok.tag[1]), "title": title, "id": slug})
    html = md.renderer.render(tokens, md.options, {})
    html = html.replace("<table>", '<div class="table-scroll"><table>').replace("</table>", "</table></div>")
    data = {"html": html, "toc": toc, "sections": {t["id"] for t in toc}}
    _cache.update(stamp=stamp, data=data)
    return data


def anchor_for(path):
    """The guide section id for a screen's URL path, or "" when there is no specific section."""
    for prefix, number in SECTION_FOR_PATH:
        if path.startswith(prefix):
            return f"s{number}"
    return ""
