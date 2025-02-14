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


import random
from mindframe.models import Intervention, CustomUser

import logging

logger = logging.getLogger(__name__)


class IndexView(LoginRequiredMixin, TemplateView):
    template_name = "index.html"


# TODO FIXME
def create_public_session(request, intervention_slug):

    # Get the intervention based on the ID
    intervention = get_object_or_404(Intervention, slug=intervention_slug)

    # Create a temporary or anonymous client (could be a placeholder user, if needed)
    sn = silly_name()
    f, l = sn.split(" ")
    client = CustomUser.objects.create(
        username=f"{slugify(sn)}{random.randint(1e4, 1e5)}",
        first_name=f,
        last_name=l,
        is_active=False,
    )

    # Generate a new cycle and session
    # cycle = Cycle.objects.create(intervention=intervention, client=client)
    # session = TreatmentSession.objects.create(cycle=cycle, started=timezone.now())
    # TODO FIXME
    session = None
    # Redirect to the chat page with the session UUID
    chat_url = f"{settings.CHAT_URL}/?session_id={session.uuid}"
    return redirect(chat_url)
