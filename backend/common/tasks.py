from django_tasks import task


@task()
def add(a, b):
    """Trivial task used to prove the worker/backend executes tasks."""
    return a + b
