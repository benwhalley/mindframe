from django.utils.text import slugify
from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings
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
from mindframe.models import Intervention, CustomUser

import logging

logger = logging.getLogger(__name__)


class IndexView(LoginRequiredMixin, TemplateView):
    template_name = "index.html"


def create_public_session(request, intervention_slug):

    intervention = get_object_or_404(Intervention, slug=intervention_slug)
    step = intervention.steps.all().first()
    turn = start_conversation(step)
    chat_url = f"{settings.CHAT_URL}/?turn_id={turn.uuid}"
    return redirect(chat_url)
