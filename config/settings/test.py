from .base import *  # noqa

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
SECRET_KEY = "test-key"
import tempfile

MEDIA_ROOT = tempfile.mkdtemp(prefix="garment-erp-test-media-")
