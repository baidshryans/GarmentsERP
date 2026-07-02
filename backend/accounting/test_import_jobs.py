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
