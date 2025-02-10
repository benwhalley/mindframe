from django.utils.text import slugify
from django.shortcuts import redirect
from django.utils import timezone
from django import forms
from django.views.generic.edit import FormMixin
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
from mindframe.synthetic import add_turns_task

import random
from mindframe.models import (
    Intervention,
    CustomUser,
    Memory,
    Turn,
    Note,
    LLM,
)

import logging

logger = logging.getLogger(__name__)


class IndexView(LoginRequiredMixin, TemplateView):
    template_name = "index.html"


class RAGHyDEComparisonForm(forms.Form):
    query = forms.CharField(
        label="Search Query",
        max_length=255,
        required=True,
        initial="therapist leading vivid imagery exercise",
        widget=forms.Textarea(attrs={"rows": 3, "cols": 20}),
    )
    top_k = forms.IntegerField(
        label="Top K Results",
        min_value=1,
        max_value=20,
        initial=3,
        help_text="Number of results to return",
    )
    window_size = forms.IntegerField(
        label="Window Size",
        min_value=0,
        max_value=5,
        initial=1,
        help_text="Number of sentences to return around the matched sentence",
    )
    intervention = forms.ModelMultipleChoiceField(
        label="Select Intervention",
        required=False,
        queryset=Intervention.objects.none(),
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if Intervention.objects.exists():
            self.fields["intervention"].queryset = Intervention.objects.all()
            self.fields["intervention"].initial = Intervention.objects.first()


class RAGHyDEComparisonView(LoginRequiredMixin, FormView):
    template_name = "rag_hyde_comparison.html"
    form_class = RAGHyDEComparisonForm
    success_url = reverse_lazy("rag_hyde_comparison")  # Redirect to the same page

    def form_valid(self, form):
        # Fetch the intervention using the provided slug
        interventions = form.cleaned_data["intervention"]
        if interventions:
            memories = Memory.objects.filter(intervention__in=interventions)
        else:
            memories = Memory.objects.all()

        # Call RAG and HyDE functions
        rag_results, _, _ = memories.search(
            form.cleaned_data["query"], top_k=form.cleaned_data["top_k"]
        )

        hyde_results, _, hyp_doc = memories.search(
            form.cleaned_data["query"],
            method="hyde",
            llm=LLM.objects.get(model_name="gpt-4o"),
            top_k=form.cleaned_data["top_k"],
        )

        # Add results to the context
        context = self.get_context_data(form=form)
        context["rag_results"] = rag_results
        context["hyde_results"] = hyde_results
        context["hyde_hypothetical_document"] = hyp_doc
        context["query"] = form.cleaned_data["query"]
        context["interventions"] = interventions
        return self.render_to_response(context)


def create_public_session(request, intervention_slug):
    pass
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


class TreatmentSessionDetailView(LoginRequiredMixin, DetailView):
    # model = TreatmentSession
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
            .prefetch_related("speaker", "session_state__step", "notes", "llm_calls")
            .order_by("timestamp")
        )

        context["states"] = session.progress.select_related("step", "previous_step")

        context["notes"] = Note.objects.filter(turn__session_state__session=session).select_related(
            "judgement"
        )

        context["data"] = session.state.step.make_data_variable(session)

        return context


# class SyntheticConversationForm(forms.Form):
#     therapist_first = forms.BooleanField(
#         required=False, initial=True, help_text="Therapist speaks first"
#     )
#     transcript = forms.CharField(
#         widget=forms.Textarea(attrs={"rows": 10, "cols": 80}),
#         initial="Hi, welcome to the session. Do you have any questions about Mindframe?",
#         help_text="Paste conversation transcript, one row per speaker. Splits on line breaks and assumes client/therapist alternate turns.",
#     )
#     add_turns = forms.IntegerField(
#         help_text="Number of new turns to generate and add to the conversation transcript.",
#         initial=0,
#         min_value=0,
#         max_value=100,
#     )

#     therapist = forms.ModelChoiceField(
#         required=False,
#         queryset=CustomUser.objects.none(),
#         help_text="Optionally select an existing therapist user",
#     )

#     client = forms.ModelChoiceField(
#         queryset=CustomUser.objects.none(),
#         required=False,
#         help_text="Optionally select an existing client user",
#     )
#     therapist_intervention = forms.ModelChoiceField(
#         required=True,
#         queryset=Intervention.objects.none(),
#         help_text="Select an intervention for the therapist",
#     )
#     client_intervention = forms.ModelChoiceField(
#         required=True,
#         queryset=Intervention.objects.none(),
#         help_text="Select an intervention for the client",
#     )

#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         if Intervention.objects.exists():
#             self.fields["therapist"].queryset = CustomUser.objects.filter(role="therapist")
#             self.fields["therapist"].initial = CustomUser.objects.filter(role="therapist").first()

#             self.fields["therapist"].queryset = CustomUser.objects.filter(role="client")

#             self.fields["client_intervention"].queryset = Intervention.objects.all()
#             self.fields["client_intervention"].initial = Intervention.objects.filter(
#                 slug__istartswith="fake-client"
#             ).first()

#             self.fields["therapist_intervention"].queryset = Intervention.objects.all()
#             self.fields["therapist_intervention"].initial = Intervention.objects.filter(
#                 slug__istartswith="demo"
#             ).first()


class SyntheticConversationCreateView(LoginRequiredMixin, FormView):
    template_name = "synthetic_conversation_form.html"
    # form_class = SyntheticConversationForm
    success_url = reverse_lazy("synthetic_conversation_detail")

    def form_valid(self, form):
        transcript = form.cleaned_data["transcript"].strip().split("\n")
        therapist = form.cleaned_data["therapist"]
        client = form.cleaned_data["client"]
        add_turns = form.cleaned_data["add_turns"]
        therapist_intervention = form.cleaned_data["therapist_intervention"]
        client_intervention = form.cleaned_data["client_intervention"]

        # Create users if not provided
        if not therapist:
            therapist = CustomUser.objects.create(
                username=f"therapist_{random.randint(1000, 9999)}", role="therapist"
            )
        if not client:
            client = CustomUser.objects.create(
                username=f"client_{random.randint(1000, 9999)}", role="client"
            )

        # Create treatment cycles and sessions
        therapist_cycle = Cycle.objects.create(
            client=therapist, intervention=therapist_intervention
        )
        client_cycle = Cycle.objects.create(client=client, intervention=client_intervention)
        therapist_session = TreatmentSession.objects.create(
            cycle=therapist_cycle, started=timezone.now()
        )
        client_session = TreatmentSession.objects.create(cycle=client_cycle, started=timezone.now())

        # Create synthetic conversation link
        conversation = SyntheticConversation.objects.create(
            session_one=therapist_session, session_two=client_session, start_time=timezone.now()
        )

        # Process transcript and assign turns
        speakers_ = (
            form.cleaned_data["therapist_first"]
            and [therapist_session, client_session]
            or [client_session, therapist_session]
        )
        speakers = cycle(speakers_)
        listeners = cycle(speakers_)
        for line, spkr in list(zip(transcript, speakers)):
            text = line.strip()
            a = listeners.__next__()
            b = listeners.__next__()
            lt = a.listen(speaker=spkr.cycle.client, text=text)
            b.listen(speaker=spkr.cycle.client, text=text)
            conversation.last_speaker_turn = lt
            conversation.save()

        if int(add_turns) > 0:
            conversation.additional_turns_scheduled += add_turns
            conversation.save()
            add_turns_task.delay(conversation.pk, add_turns)
            logger.info(
                f"Scheduled generting {add_turns} turns to conversation ID {conversation.pk}."
            )

        return redirect(
            reverse_lazy("synthetic_conversation_detail", kwargs={"pk": conversation.pk})
        )


class AdditionalTurnsForm(forms.Form):
    n_turns = forms.IntegerField(
        label="Number of Turns",
        min_value=1,
        max_value=100,
        help_text="Specify how many additional turns to generate.",
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )


class SyntheticConversationDetailView(LoginRequiredMixin, DetailView, FormMixin):
    # model = SyntheticConversation
    template_name = "synthetic_conversation_detail.html"
    context_object_name = "conversation"
    form_class = AdditionalTurnsForm  # Use the custom form

    def get_object(self, queryset=None):
        return get_object_or_404(SyntheticConversation, pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        conversation = self.get_object()

        context["turns"] = Turn.objects.filter(
            session_state__session=conversation.session_one
        ).order_by("timestamp")

        context["form"] = self.get_form()
        return context

    def get_success_url(self):
        return reverse("synthetic_conversation_detail", kwargs={"pk": self.object.pk})

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            n_turns = form.cleaned_data["n_turns"]
            self.object.additional_turns_scheduled += n_turns
            self.object.save()

            add_turns_task.delay(self.object.pk, n_turns)  # Adding N turns as specified
            return self.form_valid(form)
        else:
            return self.form_invalid(form)


# class SyntheticConversationDetailView(LoginRequiredMixin, DetailView):
#     model = SyntheticConversation
#     template_name = "synthetic_conversation_detail.html"
#     context_object_name = "conversation"

#     def get_object(self, queryset=None):
#         # Use the pk from the URL to fetch the conversation
#         return get_object_or_404(SyntheticConversation, pk=self.kwargs["pk"])

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)

#         # Fetch turns from each session in the conversation
#         conversation = self.get_object()

#         context["turns"] = Turn.objects.filter(
#             session_state__session=conversation.session_one
#         ).order_by("timestamp")

#         return context
