# MINDFRAME SPECIFIC SETTINGS

import os

import shortuuid
from decouple import config
from django.conf import settings
from django.db import models

TELEGRAM_BOT_NAME = config("TELEGRAM_BOT_NAME", None)

DEFAULT_CONVERSATION_MODEL_NAME = config("DEFAULT_CONVERSATION_MODEL_NAME", "gpt-4o-mini")
DEFAULT_JUDGEMENT_MODEL_NAME = config("DEFAULT_JUDGEMENT_MODEL_NAME", "gpt-4o-mini")
DEFAULT_CHUNKING_MODEL_NAME = config("DEFAULT_CHUNKING_MODEL_NAME", "gpt-4o")


# 24 chars in alphapbet and 22 long = 24^22 so still very large for guessing but easier to read for humans
MINDFRAME_SHORTUUID_ALPHABET = getattr(
    settings, "MINDFRAME_SHORTUUID_ALPHABET", "abcdefghjkmnpqrstuvwxyz123456789"
)

shortuuid.set_alphabet(MINDFRAME_SHORTUUID_ALPHABET)


def mfuuid():
    # uses the alphabet
    return shortuuid.uuid()


class InterventionTypes(models.TextChoices):
    THERAPY = "therapy", "A therapeutic intervention"
    CLIENT = "client", "A simulated client"


class BranchReasons(models.TextChoices):
    MAIN = "main", "Not a branch - part of the main trunk of the conversation"
    EXPERT = "expert", "Expert completion/imagined alternative"
    PLAY = "play", "Simulation/reset to create alternative line of conversation"
    UNDO = "undo", "Undo in role-play"


class TurnTextSourceTypes(models.TextChoices):
    """Types of sources for a Turn object."""

    HUMAN = "human", "Human"
    GENERATED = "generated", "AI generated"
    OPENING = "opening", "Opening"


class TurnTypes(models.TextChoices):
    """Types of Turn object."""

    HUMAN = "human", "Human utterance"
    BOT = "bot", "Bot utterance"
    OPENING = "opening", "Fixed opening line"
    JOIN = "join", "Join"  # joining a conversation
    # LEFT = "left", "Left" # joining a conversation


class RoleChoices(models.TextChoices):
    """Defines various roles in the system such as developers, clients, and supervisors."""

    SYSTEM_DEVELOPER = "system_developer", "System Developer"
    INTERVENTION_DEVELOPER = "intervention_developer", "Intervention Developer"
    CLIENT = "client", "Client"
    SUPERVISOR = "supervisor", "Supervisor"
    THERAPIST = "therapist", "Therapist"
    BOT = "bot", "Bot"


class StepJudgementFrequencyChoices(models.TextChoices):
    """Specifies when/how frequently a judgement should be made during a step."""

    TURN = "turn", "Every n turns"
    ENTER = "enter", "When entering the step"
    EXIT = "exit", "When exiting the step"


OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
