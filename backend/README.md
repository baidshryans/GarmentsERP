do another table entry

barcode marking done

ask Shryans ->

Multi table entry should be done

1. barcode that is sold should be marked

## Background jobs

Background tasks (CRM sends; later PDF/imports) run via Django's tasks framework
with the `django-tasks-db` database backend.

- **Worker:** run `start-worker-dev.bat` (dev) or `python manage.py db_worker`
  under systemd / NSSM (prod). Required for any background task to execute.
- **CRM trigger:** schedule `python manage.py run_due_crm` to run every minute.
  It enqueues due birthday/anniversary sends; the worker performs the WhatsApp I/O.
  - Linux (crontab):
    `* * * * * cd /path/to/backend && /path/to/env/bin/python manage.py run_due_crm`
  - Windows: a Task Scheduler task, trigger "repeat every 1 minute", action
    `env\Scripts\python.exe manage.py run_due_crm`, started in the backend folder.

