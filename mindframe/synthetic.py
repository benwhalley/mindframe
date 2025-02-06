from django.shortcuts import get_object_or_404
from mindframe.models import SyntheticConversation, TurnSourceTypes
from django.db.models import Q
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


def add_turns(conversation: SyntheticConversation, n_turns: int):
    """
    Adds N additional turns to a SyntheticConversation, ensuring alternating speakers.
    """

    for i in range(n_turns):
        # work out who should speak
        last_speaker = conversation.last_speaker_turn.session_state.session.cycle.client
        logger.warning(f"LAST SPEAKER: {last_speaker}")

        if last_speaker != conversation.session_one.cycle.client:
            speaker = conversation.session_two
            listener = conversation.session_one
        else:
            speaker = conversation.session_one
            listener = conversation.session_two

        utt = speaker.respond().get("utterance", "???")
        conversation.last_speaker_turn = listener.listen(
            text=utt, speaker=speaker.cycle.client, source_type=TurnSourceTypes.AI
        )
        conversation.additional_turns_scheduled -= 1
        conversation.save()

    logger.info(f"Completed {n_turns} additional turns in conversation ID {conversation.pk}.")
    return conversation


# add_turns(SyntheticConversation.objects.get(id=36), 2)


@shared_task
def add_turns_task(conversation_pk: int, n_turns: int):
    """
    Celery task to add N additional turns to a SyntheticConversation.
    """
    conversation = get_object_or_404(SyntheticConversation, pk=conversation_pk)
    add_turns(conversation, n_turns)
