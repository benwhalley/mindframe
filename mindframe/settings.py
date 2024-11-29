# MINDFRAME SPECIFIC SETTINGS

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from types import SimpleNamespace
import os


# 24 chars in alphapbet and 22 long = 24^22 so still very large for guessing but easier to read for humans
MINDFRAME_SHORTUUID_ALPHABET = getattr(
    settings, "MINDFRAME_SHORTUUID_ALPHABET", "abcdefghjkmnpqrstuvwxyz"
)

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
