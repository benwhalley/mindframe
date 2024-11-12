# MINDFRAME SPECIFIC SETTINGS
import warnings
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from types import SimpleNamespace

from magentic import OpenaiChatModel
from magentic.chat_model.litellm_chat_model import LitellmChatModel


MINDFRAME_AI_MODELS = getattr(
    settings,
    "MINDFRAME_AI_MODELS",
    SimpleNamespace(
        free=LitellmChatModel("ollama_chat/llama3.2", api_base="http://localhost:11434"),
        expensive=OpenaiChatModel("gpt-4o", api_type="azure"),
        cheap=OpenaiChatModel("gpt-4o-mini", api_type="azure"),
    ),
)

# 24 chars in alphapbet and 22 long = 24^22 so still very large for guessing but easier to read for humans
MINDFRAME_SHORTUUID_ALPHABET = getattr(
    settings, "MINDFRAME_SHORTUUID_ALPHABET", "abcdefghjkmnpqrstuvwxyz"
)
