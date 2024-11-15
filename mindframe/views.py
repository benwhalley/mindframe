from itertools import chain
from django.utils.text import slugify
from django.shortcuts import redirect
from django.utils import timezone
from .models import Intervention, Cycle, TreatmentSession, CustomUser
from django.db.models import Q
from django.conf import settings
from django.shortcuts import get_object_or_404
import shortuuid
from mindframe.silly import silly_name
import random
from django.http import JsonResponse
from mindframe.models import Intervention, CustomUser, TreatmentSession, SyntheticConversation, Turn
from django.views.generic.detail import DetailView


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


class SyntheticConversationDetailView(DetailView):
    model = SyntheticConversation
    template_name = "synthetic_conversation_detail.html"
    context_object_name = "conversation"

    def get_object(self, queryset=None):
        # Use the pk from the URL to fetch the conversation
        return get_object_or_404(SyntheticConversation, pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Fetch turns from each session in the conversation
        conversation = self.get_object()

        context["turns"] = Turn.objects.filter(
            session_state__session=conversation.session_one
        ).order_by("timestamp")

        return context
