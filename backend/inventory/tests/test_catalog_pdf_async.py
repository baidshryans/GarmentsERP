from django.test import TestCase, override_settings

IMMEDIATE = {"default": {"BACKEND": "django_tasks.backends.immediate.ImmediateBackend"}}


class BuildCatalogPdfBytesTests(TestCase):
    def test_returns_pdf_bytes_even_when_empty(self):
        from inventory.catalog_pdf_service import build_catalog_pdf_bytes

        data, filename = build_catalog_pdf_bytes({}, None, "summary")

        self.assertEqual(data[:5], b"%PDF-", "output should be a PDF")
        self.assertTrue(filename.endswith(".pdf"))
