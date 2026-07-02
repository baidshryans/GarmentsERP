from django.test import SimpleTestCase, override_settings

IMMEDIATE = {"default": {"BACKEND": "django_tasks.backends.immediate.ImmediateBackend"}}


@override_settings(TASKS=IMMEDIATE)
class SmokeTaskTests(SimpleTestCase):
    def test_smoke_task_runs_and_returns(self):
        from common.tasks import add

        result = add.enqueue(2, 3)
        self.assertEqual(result.return_value, 5)
