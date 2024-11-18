# MINDFRAME SPECIFIC SETTINGS
import warnings
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from types import SimpleNamespace

from magentic import OpenaiChatModel
from magentic.chat_model.litellm_chat_model import LitellmChatModel

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
        free=LitellmChatModel("ollama_chat/llama3.2", api_base="http://localhost:11434"),
        expensive=OpenaiChatModel("gpt-4o", api_type="azure"),
        cheap=OpenaiChatModel("gpt-4o-mini", api_type="azure"),
        embedding=LazySentenceTransformer("sentence-transformers/all-MiniLM-L6-v2"),
    ),
)

# 24 chars in alphapbet and 22 long = 24^22 so still very large for guessing but easier to read for humans
MINDFRAME_SHORTUUID_ALPHABET = getattr(
    settings, "MINDFRAME_SHORTUUID_ALPHABET", "abcdefghjkmnpqrstuvwxyz"
)
