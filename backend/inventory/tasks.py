import uuid

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django_tasks import task


@task()
def generate_catalog_pdf(params, retail_id, fmt):
    """Build the catalog PDF in the background, save it to MEDIA, return its URL."""
    from inventory.catalog_pdf_service import build_catalog_pdf_bytes

    pdf_bytes, filename = build_catalog_pdf_bytes(params, retail_id, fmt)
    name = f"catalog_pdfs/{uuid.uuid4().hex}_{filename}"
    saved = default_storage.save(name, ContentFile(pdf_bytes))
    return default_storage.url(saved)
