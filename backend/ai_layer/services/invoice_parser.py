"""
InvoiceParserService — GPT-4o Vision extracts purchase invoice fields.

Accepts a JPG/PNG/PDF file, encodes it as base64, and asks GPT-4o to return
structured JSON with vendor details, line items, and tax amounts.
"""

import base64
import json
import logging
from io import BytesIO

from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)

# Lazy client — instantiated on first use so missing API key doesn't crash startup
_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


EXTRACTION_PROMPT = """Extract the following fields from this purchase invoice image and return ONLY valid JSON.

Required JSON structure:
{
  "vendor_name": "string — supplier / seller name",
  "invoice_number": "string",
  "invoice_date": "string — YYYY-MM-DD format",
  "place_of_supply": "string — state name or code",
  "gstin_vendor": "string — GST registration number of vendor, or null",
  "items": [
    {
      "description": "string — item description",
      "hsn_code": "string or null",
      "quantity": number,
      "unit": "string e.g. gm, pcs, nos",
      "gross_weight_gm": number or null,
      "net_weight_gm": number or null,
      "purity": "string e.g. 22K, 18K, 916, 750, or null",
      "rate_per_gram": number or null,
      "amount": number
    }
  ],
  "cgst_amount": number or null,
  "sgst_amount": number or null,
  "igst_amount": number or null,
  "total_amount": number,
  "notes": "string — any other relevant notes, or null"
}

Rules:
- All monetary values should be plain numbers (no currency symbols or commas).
- If a field is not found, use null.
- Do not include any text outside the JSON object.
- Dates must be in YYYY-MM-DD format; if only partial date is visible, make your best guess.
"""


def _encode_image(file_bytes: bytes, mime_type: str) -> str:
    """Return base64-encoded image data URL."""
    b64 = base64.b64encode(file_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{b64}"


def _pdf_first_page_to_image(file_bytes: bytes) -> tuple[bytes, str]:
    """
    Convert the first page of a PDF to a JPEG image using pillow + pypdf.
    Falls back to returning the raw bytes as application/pdf if conversion fails
    (GPT-4o can sometimes handle PDFs directly via data URL).
    """
    try:
        from pypdf import PdfReader
        from PIL import Image
        import fitz  # PyMuPDF

        doc = fitz.open(stream=file_bytes, filetype="pdf")
        page = doc[0]
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("jpeg")
        return img_bytes, "image/jpeg"
    except Exception:
        # If PyMuPDF not available, return raw PDF bytes and let GPT handle it
        return file_bytes, "application/pdf"


def parse_invoice(file_bytes: bytes, filename: str) -> dict:
    """
    Parse a purchase invoice image or PDF using GPT-4o Vision.

    Args:
        file_bytes: Raw file bytes
        filename: Original filename (used to determine MIME type)

    Returns:
        dict with extracted fields, or {"error": "..."} on failure
    """
    if not settings.OPENAI_API_KEY:
        return {"error": "OpenAI API key not configured. Set OPENAI_API_KEY environment variable."}

    # Determine MIME type
    fname_lower = filename.lower()
    if fname_lower.endswith(".pdf"):
        file_bytes, mime_type = _pdf_first_page_to_image(file_bytes)
        # If still PDF, use the PDF mime type
        if mime_type == "application/pdf":
            # Try to pass as PDF; GPT-4o may not support PDF directly — warn
            logger.warning("PyMuPDF not installed; sending raw PDF bytes to GPT-4o (may fail).")
    elif fname_lower.endswith(".png"):
        mime_type = "image/png"
    elif fname_lower.endswith(".jpg") or fname_lower.endswith(".jpeg"):
        mime_type = "image/jpeg"
    elif fname_lower.endswith(".webp"):
        mime_type = "image/webp"
    else:
        mime_type = "image/jpeg"  # assume JPEG as fallback

    image_data_url = _encode_image(file_bytes, mime_type)

    client = _get_client()

    try:
        response = client.chat.completions.create(
            model=settings.AI_VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": EXTRACTION_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": image_data_url, "detail": "high"},
                        },
                    ],
                }
            ],
            response_format={"type": "json_object"},
            max_tokens=2000,
        )

        raw_json = response.choices[0].message.content
        parsed = json.loads(raw_json)

        # Normalise: ensure items is a list
        if "items" not in parsed or not isinstance(parsed["items"], list):
            parsed["items"] = []

        logger.info(
            "Invoice parsed successfully: vendor=%s, total=%s",
            parsed.get("vendor_name"),
            parsed.get("total_amount"),
        )
        return parsed

    except json.JSONDecodeError as e:
        logger.error("GPT returned invalid JSON for invoice parse: %s", e)
        return {"error": f"Failed to parse JSON from AI response: {e}"}
    except Exception as e:
        logger.error("Invoice parsing failed: %s", e)
        return {"error": str(e)}
