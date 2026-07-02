import io
import os
import shutil

from django.core.management import call_command
from django.core.management.base import CommandError
from django_tasks import task


@task()
def run_import_job(job_id, command, path_kwargs, apply, job_dir):
    """Run a legacy import command in the background, recording the result on ImportJob."""
    from common.models import ImportJob

    job = ImportJob.objects.get(id=job_id)
    job.status = "RUNNING"
    job.save(update_fields=["status", "updated_at"])

    buf = io.StringIO()
    try:
        kwargs = dict(path_kwargs)
        kwargs.update(apply=apply, continue_on_error=True, report_dir=job_dir)
        try:
            call_command(command, stdout=buf, stderr=buf, **kwargs)
        except CommandError as exc:
            job.status = "FAILED"
            job.error = str(exc)
            job.output = buf.getvalue()
            job.save(update_fields=["status", "error", "output", "updated_at"])
            return

        reports = {}
        for fn in os.listdir(job_dir):
            if fn.startswith("unresolved") or fn.startswith("imbalanced"):
                with open(os.path.join(job_dir, fn), encoding="utf-8") as r:
                    reports[fn] = r.read()[:20000]

        job.status = "COMPLETED"
        job.applied = apply
        job.output = buf.getvalue()
        job.reports = reports
        job.save(update_fields=["status", "applied", "output", "reports", "updated_at"])
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)
