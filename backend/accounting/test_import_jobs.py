from django.test import TestCase


class ImportJobModelTests(TestCase):
    def test_defaults(self):
        from common.models import ImportJob
        job = ImportJob.objects.create(kind="vouchers")
        self.assertEqual(job.status, "PENDING")
        self.assertFalse(job.applied)
        self.assertEqual(job.output, "")
        self.assertEqual(job.reports, {})


from unittest.mock import patch
from django.test import override_settings

IMMEDIATE = {"default": {"BACKEND": "django_tasks.backends.immediate.ImmediateBackend"}}


@override_settings(TASKS=IMMEDIATE)
class RunImportJobTaskTests(TestCase):
    def _job_dir(self):
        import tempfile
        return tempfile.mkdtemp(prefix="test_import_")

    def test_success_sets_completed_and_captures_output(self):
        from common.models import ImportJob
        from accounting.tasks import run_import_job

        job = ImportJob.objects.create(kind="vouchers")
        job_dir = self._job_dir()

        def fake_cmd(command, stdout=None, stderr=None, **kwargs):
            stdout.write("imported 5 rows")

        with patch("accounting.tasks.call_command", side_effect=fake_cmd):
            run_import_job.enqueue(job.id, "import_vouchers", {"main": "m.csv"}, True, job_dir)

        job.refresh_from_db()
        self.assertEqual(job.status, "COMPLETED")
        self.assertIn("imported 5 rows", job.output)
        self.assertTrue(job.applied)

    def test_command_error_sets_failed(self):
        from common.models import ImportJob
        from accounting.tasks import run_import_job
        from django.core.management.base import CommandError

        job = ImportJob.objects.create(kind="vouchers")
        job_dir = self._job_dir()

        with patch("accounting.tasks.call_command", side_effect=CommandError("bad file")):
            run_import_job.enqueue(job.id, "import_vouchers", {"main": "m.csv"}, False, job_dir)

        job.refresh_from_db()
        self.assertEqual(job.status, "FAILED")
        self.assertIn("bad file", job.error)


from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from django.core.files.uploadedfile import SimpleUploadedFile


class ImportEndpointTests(TestCase):
    # Uses the real DatabaseBackend; no worker runs in tests, so the job stays
    # PENDING. Verifies start creates a job + status is pollable. Task execution
    # is covered by RunImportJobTaskTests.
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="imp", password="p")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_start_creates_job_then_status(self):
        files = {
            "main": SimpleUploadedFile("main.csv", b"a,b\n1,2\n"),
            "details": SimpleUploadedFile("details.csv", b"a,b\n1,2\n"),
        }
        start = self.client.post(
            "/accounting/api/migration/vouchers/async/?apply=false", files, format="multipart",
        )
        self.assertEqual(start.status_code, 200)
        job_id = start.json()["job_id"]

        status = self.client.get(f"/accounting/api/migration/job/{job_id}/")
        self.assertEqual(status.status_code, 200)
        body = status.json()
        self.assertEqual(body["kind"], "vouchers")
        self.assertIn(body["status"], ("PENDING", "RUNNING", "COMPLETED", "FAILED"))
