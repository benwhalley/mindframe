from django.utils.text import slugify
from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from mindframe.silly import silly_name
from django.views.generic.detail import DetailView
from django.views.generic.base import TemplateView
from django.views.generic.edit import FormView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from itertools import cycle
from mindframe.conversation import add_turns_task
from mindframe.conversation import start_conversation
import random
from mindframe.models import Intervention, CustomUser, Turn

from django.contrib.auth.decorators import login_required
from django.core import signing
from django.shortcuts import render


import logging

logger = logging.getLogger(__name__)


class IndexView(LoginRequiredMixin, TemplateView):
    template_name = "index.html"


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
        turn = start_conversation(step)
        logger.info(f"Starting chat with intervention {intervention} using new turn {turn.uuid}")
    elif step_id:
        step = get_object_or_404(Step, pk=step_id)
        turn = start_conversation(step)

    token = signing.dumps(
        {
            "turn_uuid": turn.uuid,
        },
        salt="gradio-chatbot-auth",
    )

    chat_url = f"{settings.CHAT_URL}?token={token}"
    return redirect(chat_url)
