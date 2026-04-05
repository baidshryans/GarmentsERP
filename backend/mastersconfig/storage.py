"""
Dynamic attachment storage backend.

Reads the root directory from SystemSettings at the time of each file
operation. Falls back to <MEDIA_ROOT>/purchase_attachments/ when no
path is configured in settings.
"""

import os
from django.conf import settings
from django.core.files.storage import Storage


def _configured_root():
    """Return the currently configured attachment storage root path."""
    try:
        from mastersconfig.models import SystemSettings
        path = (
            SystemSettings.objects.filter(pk=1)
            .values_list('attachment_storage_path', flat=True)
            .first()
        )
        if path and path.strip():
            return path.strip()
    except Exception:
        pass
    # Default: MEDIA_ROOT (existing files at MEDIA_ROOT/purchase_attachments/... stay intact)
    return settings.MEDIA_ROOT


class DynamicAttachmentStorage(Storage):
    """
    File-system storage whose root directory is resolved dynamically from
    SystemSettings on every file operation.

    Files are served through /purchase/api/attachment-file/<name>
    so they are accessible regardless of whether they live inside or
    outside MEDIA_ROOT.
    """

    # ── Save ─────────────────────────────────────────────────────────────────

    def _save(self, name, content):
        root = _configured_root()
        full_path = os.path.normpath(os.path.join(root, name))

        # Ensure the directory tree exists
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        # Write chunks to disk
        with open(full_path, 'wb') as dest:
            for chunk in content.chunks():
                dest.write(chunk)

        return name

    # ── Read / Introspect ─────────────────────────────────────────────────────

    def path(self, name):
        return os.path.normpath(os.path.join(_configured_root(), name))

    def exists(self, name):
        return os.path.exists(self.path(name))

    def size(self, name):
        return os.path.getsize(self.path(name))

    def url(self, name):
        """Return a URL served by the dedicated attachment-file view."""
        from urllib.parse import quote
        # Keep slashes intact so subdirectory structure is preserved in the URL.
        return '/purchase/api/attachment-file/' + quote(name, safe='/')

    # ── Delete ────────────────────────────────────────────────────────────────

    def delete(self, name):
        try:
            p = self.path(name)
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass

    # ── Stable deconstruct (prevents spurious migrations) ─────────────────────

    def deconstruct(self):
        return ('mastersconfig.storage.DynamicAttachmentStorage', [], {})


# ── Barcode image storage ────────────────────────────────────────────────────

def _barcode_image_root():
    """Return the currently configured barcode image storage root path."""
    try:
        from mastersconfig.models import SystemSettings
        path = (
            SystemSettings.objects.filter(pk=1)
            .values_list('barcode_image_storage_path', flat=True)
            .first()
        )
        if path and path.strip():
            return path.strip()
    except Exception:
        pass
    return settings.MEDIA_ROOT


class DynamicBarcodeImageStorage(Storage):
    """
    File-system storage for barcode images whose root directory is resolved
    dynamically from SystemSettings.barcode_image_storage_path.

    Files are served through /inventory/api/barcode-image-file/<name>
    """

    def _save(self, name, content):
        root = _barcode_image_root()
        full_path = os.path.normpath(os.path.join(root, name))
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'wb') as dest:
            for chunk in content.chunks():
                dest.write(chunk)
        return name

    def path(self, name):
        return os.path.normpath(os.path.join(_barcode_image_root(), name))

    def exists(self, name):
        return os.path.exists(self.path(name))

    def size(self, name):
        return os.path.getsize(self.path(name))

    def url(self, name):
        from urllib.parse import quote
        return '/inventory/api/barcode-image-file/' + quote(name, safe='/')

    def delete(self, name):
        try:
            p = self.path(name)
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass

    def deconstruct(self):
        return ('mastersconfig.storage.DynamicBarcodeImageStorage', [], {})
