from django.utils.text import slugify
from django.shortcuts import redirect
from django.utils import timezone

from django.conf import settings
from django.shortcuts import get_object_or_404
from mindframe.silly import silly_name
import random
from mindframe.models import (
    Intervention,
    Cycle,
    CustomUser,
    TreatmentSession,
    SyntheticConversation,
    Turn,
    LLMLog,
    Note,
)
from django.views.generic.detail import DetailView
from django.views.generic.base import TemplateView
from django import forms
from django.views.generic.edit import FormView
from django.urls import reverse_lazy
from mindframe.rag import rag_examples, hyde_examples
from django.contrib.auth.mixins import LoginRequiredMixin

from django.utils.safestring import mark_safe


class IndexView(LoginRequiredMixin, TemplateView):
    template_name = "index.html"


class RAGHyDEComparisonForm(forms.Form):
    query = forms.CharField(label="Search Query", max_length=255, required=True)
    top_k = forms.IntegerField(label="Top K Results", min_value=1, max_value=20, initial=3)
    window_size = forms.IntegerField(label="Window Size", min_value=1, max_value=10, initial=2)
    intervention = forms.ModelChoiceField(
        queryset=Intervention.objects.all(),
        label="Select Intervention",
        empty_label="Select an Intervention",
        required=True,
        initial=lambda: Intervention.objects.first(),
    )


class RAGHyDEComparisonView(LoginRequiredMixin, FormView):
    template_name = "rag_hyde_comparison.html"
    form_class = RAGHyDEComparisonForm
    success_url = reverse_lazy("rag_hyde_comparison")  # Redirect to the same page

    def form_valid(self, form):
        # Fetch the intervention using the provided slug
        intervention = form.cleaned_data["intervention"]

        interventions = Intervention.objects.filter(pk__in=[intervention.pk])
        # Extract form data
        query = form.cleaned_data["query"]
        top_k = form.cleaned_data["top_k"]
        window_size = form.cleaned_data["window_size"]

        # Call RAG and HyDE functions
        rag_results = rag_examples(
            query, top_k=top_k, window_size=window_size, interventions=interventions
        )
        hyde_results, hyde_query = hyde_examples(
            query, top_k=top_k, window_size=window_size, interventions=interventions
        )

        # Add results to the context
        context = self.get_context_data(form=form)
        context["rag_results"] = rag_results
        context["hyde_results"] = hyde_results
        context["hyde_query"] = hyde_query
        context["query"] = query
        context["intervention"] = intervention
        return self.render_to_response(context)


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
    chat_url = f"{settings.CHAT_URL}/?session_id={session.uuid}"
    return redirect(chat_url)


class SyntheticConversationDetailView(LoginRequiredMixin, DetailView):
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


class TreatmentSessionDetailView(LoginRequiredMixin, DetailView):
    model = TreatmentSession
    template_name = "treatment_session_detail.html"
    context_object_name = "session"
    slug_field = "uuid"
    slug_url_kwarg = "uuid"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        session = self.object

        # Prefetch related data for performance
        context["turns"] = (
            Turn.objects.filter(session_state__session__uuid=session.uuid)
            .prefetch_related("speaker", "session_state__step")
            .order_by("timestamp")
        )

        context["states"] = session.progress.select_related("step", "previous_step")
        context["logs"] = LLMLog.objects.filter(session=session).select_related(
            "step", "judgement", "model"
        )
        from box import Box

        context["notes"] = Note.objects.filter(turn__session_state__session=session).select_related(
            "judgement"
        )

        context["data"] = session.state.step.make_data_variable(session)

        return context
