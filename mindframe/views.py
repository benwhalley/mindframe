from django.utils.text import slugify
from django.shortcuts import redirect
from django.utils import timezone
from .models import Intervention, Cycle, TreatmentSession, CustomUser
from django.conf import settings
from django.shortcuts import get_object_or_404
import shortuuid
from mindframe.silly import silly_name
import random


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
    cycle = Cycle.objects.create(intervention=intervention, client=client)
    session = TreatmentSession.objects.create(cycle=cycle, started=timezone.now())

    # Redirect to the chat page with the session UUID
    chat_url = f"{settings.CHATBOT_URL}/?session_id={session.uuid}"
    return redirect(chat_url)
