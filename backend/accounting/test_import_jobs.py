from django.test import TestCase


class ImportJobModelTests(TestCase):
    def test_defaults(self):
        from common.models import ImportJob
        job = ImportJob.objects.create(kind="vouchers")
        self.assertEqual(job.status, "PENDING")
        self.assertFalse(job.applied)
        self.assertEqual(job.output, "")
        self.assertEqual(job.reports, {})
