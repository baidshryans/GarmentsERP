"""Code 128 (subset B) barcodes as inline SVG: no dependency, prints crisply on any label printer."""

# Bar/space widths for symbol values 0..106 (106 = stop, 13 modules; the rest are 11 modules).
PATTERNS = (
    "212222 222122 222221 121223 121322 131222 122213 122312 132212 221213 221312 231212 112232 122132 122231 "
    "113222 123122 123221 223211 221132 221231 213212 223112 312131 311222 321122 321221 312212 322112 322211 "
    "212123 212321 232121 111323 131123 131321 112313 132113 132311 211313 231113 231311 112133 112331 132131 "
    "113123 113321 133121 313121 211331 231131 213113 213311 213131 311123 311321 331121 312113 312311 332111 "
    "314111 221411 431111 111224 111422 121124 121421 141122 141221 112214 112412 122114 122411 142112 142211 "
    "241211 221114 413111 241112 134111 111242 121142 121241 114212 124112 124211 411212 421112 421211 212141 "
    "214121 412121 111143 111341 131141 114113 114311 411113 411311 113141 114131 311141 411131 211412 211214 "
    "211232 2331112"
).split()
START_B, STOP = 104, 106


def symbol_values(text: str):
    """Symbol values for start, data, checksum and stop."""
    if not text:
        raise ValueError("A barcode needs some text.")
    values = []
    for ch in text:
        code = ord(ch) - 32
        if not 0 <= code <= 95:
            raise ValueError(f"Character {ch!r} cannot be encoded in Code 128 B.")
        values.append(code)
    checksum = (START_B + sum(i * v for i, v in enumerate(values, start=1))) % 103
    return [START_B, *values, checksum, STOP]


def modules(text: str):
    """Alternating bar / space widths, starting with a bar."""
    widths = []
    for v in symbol_values(text):
        widths += [int(c) for c in PATTERNS[v]]
    return widths


def svg(text: str, *, module_px: float = 2.0, height: int = 60, quiet: int = 10) -> str:
    """The barcode as an <svg> string. Colours use currentColor so print and themes decide."""
    widths = modules(text)
    total = sum(widths) + 2 * quiet
    x = quiet
    rects = []
    for i, w in enumerate(widths):
        if i % 2 == 0:
            rects.append(f'<rect x="{x}" y="0" width="{w}" height="{height}"/>')
        x += w
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total} {height}" width="{total * module_px:.0f}" '
        f'height="{height}" role="img" aria-label="Barcode {text}" fill="currentColor" shape-rendering="crispEdges">'
        + "".join(rects) + "</svg>"
    )
