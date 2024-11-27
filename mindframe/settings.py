# MINDFRAME SPECIFIC SETTINGS

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from types import SimpleNamespace
import os

from sentence_transformers import SentenceTransformer


class LazySentenceTransformer(object):
    def __init__(self, model_name):
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        if self._model is None:  # Load the model only when accessed
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def encode(self, *args, **kwargs):
        # Proxy the call to the actual model's encode method
        return self.model.encode(*args, **kwargs)


MINDFRAME_AI_MODELS = getattr(
    settings,
    "MINDFRAME_AI_MODELS",
    SimpleNamespace(
        embedding=LazySentenceTransformer("sentence-transformers/all-MiniLM-L6-v2"),
    ),
)

# 24 chars in alphapbet and 22 long = 24^22 so still very large for guessing but easier to read for humans
MINDFRAME_SHORTUUID_ALPHABET = getattr(
    settings, "MINDFRAME_SHORTUUID_ALPHABET", "abcdefghjkmnpqrstuvwxyz"
)

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
