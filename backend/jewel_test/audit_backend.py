"""
Custom easyaudit signals backend.

Wraps the default Django backend and silently swallows OperationalError
so that CRUD signals fired during `python manage.py migrate` don't crash
when the easyaudit tables haven't been created yet.
"""
from django.db import OperationalError
from easyaudit.backends import ModelBackend


class SafeAuditBackend(ModelBackend):
    def crud(self, crud_info):
        try:
            return super().crud(crud_info)
        except OperationalError:
            pass

    def login(self, login_info):
        try:
            return super().login(login_info)
        except OperationalError:
            pass

    def request(self, request_info):
        try:
            return super().request(request_info)
        except OperationalError:
            pass
