from django.test import TestCase, override_settings

IMMEDIATE = {"default": {"BACKEND": "django_tasks.backends.immediate.ImmediateBackend"}}


class BuildCatalogPdfBytesTests(TestCase):
    def test_returns_pdf_bytes_even_when_empty(self):
        from inventory.catalog_pdf_service import build_catalog_pdf_bytes

        data, filename = build_catalog_pdf_bytes({}, None, "summary")

        self.assertEqual(data[:5], b"%PDF-", "output should be a PDF")
        self.assertTrue(filename.endswith(".pdf"))


@override_settings(TASKS=IMMEDIATE)
class GenerateCatalogPdfTaskTests(TestCase):
    def test_task_saves_pdf_and_returns_url(self):
        from inventory.tasks import generate_catalog_pdf
        from django.core.files.storage import default_storage
        from django_tasks import TaskResultStatus

        result = generate_catalog_pdf.enqueue({}, None, "summary")

        self.assertEqual(result.status, TaskResultStatus.SUCCESSFUL)
        url = result.return_value
        self.assertTrue(url.endswith(".pdf"))
        name = "catalog_pdfs/" + url.split("catalog_pdfs/", 1)[-1]
        self.assertTrue(default_storage.exists(name))
