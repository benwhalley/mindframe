import logging
import random
from itertools import cycle

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core import signing
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.text import slugify
from django.views.generic.detail import DetailView
from django.views.generic.edit import FormView

from mindframe.conversation import add_turns_task, start_conversation
from mindframe.models import CustomUser, Intervention, Turn
from mindframe.silly import silly_name

logger = logging.getLogger(__name__)


def start_gradio_chat(
    request, turn_uuid=None, intervention_slug=None, step_id=None
) -> HttpResponseRedirect:
    if not turn_uuid and not intervention_slug and not step_id:
        raise ValueError(
            "You must provide either a Turn, Intervention slug, or Step ID to start a Gradio chat."
        )

    if turn_uuid:
        turn = get_object_or_404(Turn, uuid=turn_uuid)
    elif intervention_slug:
        intervention = get_object_or_404(Intervention, slug=intervention_slug)
        step = intervention.steps.all().first()
        turn = start_conversation(first_speaker_step=step)
        logger.info(f"Starting chat with intervention {intervention} using new turn {turn.uuid}")
    elif step_id:
        step = get_object_or_404(Step, pk=step_id)
        turn = start_conversation(step)

    token = signing.dumps(
        {
            "turn_uuid": turn.uuid,
            "human_user": request.user.pk,
        },
        salt="gradio-chatbot-auth",
    )

    chat_url = f"{settings.CHAT_URL}?token={token}"
    return redirect(chat_url)
