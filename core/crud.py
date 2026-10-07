"""Generic delete for master records.

A master can be deleted only while nothing refers to it. Anything in use is blocked by the database
(PROTECT foreign keys) and the user is told to mark it inactive instead. Posted documents are never
deleted; they are cancelled or reversed (non-negotiable rule 1). Delete needs the screen's edit permission.
"""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import ProtectedError, RestrictedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from core.exceptions import BusinessRuleError
from core.scoping import ScreenPermissionMixin


class ObjectDelete(LoginRequiredMixin, ScreenPermissionMixin, View):
    """Confirm page on GET, delete on POST. Subclasses say which object, where to go after, and what to call it."""

    screen_action = "edit"
    success_url_name = None
    noun = "record"

    def get_object(self, request, pk):
        raise NotImplementedError

    def success_url_args(self, obj):
        return ()

    def blocked_reason(self, obj):
        """Return a sentence if this record may never be deleted, else None."""
        return None

    def perform_delete(self, obj):
        """Delete the record. Override to go through a service that also removes what the record owns."""
        obj.delete()

    def _back(self, obj):
        return redirect(self.success_url_name, *self.success_url_args(obj))

    def get(self, request, pk):
        obj = self.get_object(request, pk)
        return render(request, "core/confirm_delete.html", {
            "obj": obj, "noun": self.noun, "blocked": self.blocked_reason(obj),
            "cancel_url": self._back(obj).url,
        })

    def post(self, request, pk):
        obj = self.get_object(request, pk)
        reason = self.blocked_reason(obj)
        if reason:
            messages.error(request, reason)
            return self._back(obj)
        name = str(obj)
        back = self._back(obj)
        try:
            with transaction.atomic():
                self.perform_delete(obj)
        except (ProtectedError, RestrictedError):
            messages.error(request, f"'{name}' is used by other records, so it cannot be deleted. "
                                    "Mark it inactive instead; it then stops appearing in pick lists.")
        except BusinessRuleError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"{self.noun.capitalize()} '{name}' deleted.")
        return back
