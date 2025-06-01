# budgeting.py

import logging
from typing import Tuple

from glom import Coalesce, glom

from llmtools.models import LLMCredentials

from .models import Turn
from .tree import conversation_history

logger = logging.getLogger(__name__)


def get_credentials(turn, user=None) -> LLMCredentials:
    try:
        crd = glom(
            turn,
            Coalesce(
                "conversation.user_referal.usage_plan.llm_credentials",
            ),
        )
        logger.info(f"Found credentials: {crd}")
        return crd
    except Exception as e:
        raise Exception("No LLMCredentials object found to use as default.")


def budget_exceeded(turn: Turn) -> Tuple[bool, str]:
    """Check if there is budget allocated for this conversation."""
    history = conversation_history(turn, to_leaf=True)
    N = len(history) + 1  # accounting for JOIN turn
    tuid = glom(turn, "conversation.uuid", default=None)

    co_max_turns = glom(turn, "conversation.user_referal.usage_plan.max_conversation_turns") or 0
    pl_max_turns = glom(turn, "conversation.user_referal.usage_plan.max_conversation_turns") or 0

    if N >= co_max_turns:
        return (True, "Conversation length has reached its maximum number of turns.")
    elif N > pl_max_turns:
        return (True, f"Conversation  has reached its usage plan limit.")

    return (False, "")
