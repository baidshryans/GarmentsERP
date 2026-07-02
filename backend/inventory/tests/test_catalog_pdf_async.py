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


class CatalogPdfEndpointTests(TestCase):
    # NB: uses the real DatabaseBackend (not ImmediateBackend) because the status
    # endpoint calls get_result, which ImmediateBackend does not support. With no
    # worker running in tests, a queued job reads back as READY — this verifies
    # the start + status plumbing. The SUCCESSFUL path is covered by the
    # task-level test above (GenerateCatalogPdfTaskTests).
    def setUp(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        User = get_user_model()
        self.user = User.objects.create_user(username="u1", password="p")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_start_returns_job_id_and_status_is_pollable(self):
        start = self.client.post("/inventory/api/catalog/pdf/async/?fmt=summary")
        self.assertEqual(start.status_code, 200)
        job_id = start.json()["job_id"]
        self.assertTrue(job_id)

        status = self.client.get(f"/inventory/api/catalog/pdf/job/{job_id}/")
        self.assertEqual(status.status_code, 200)
        self.assertIn(status.json()["status"], ("READY", "RUNNING", "SUCCESSFUL"))
