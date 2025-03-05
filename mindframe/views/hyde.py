import logging
import random
from itertools import cycle

from django import forms
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.text import slugify
from django.views.generic.base import TemplateView
from django.views.generic.detail import DetailView
from django.views.generic.edit import FormMixin, FormView

from mindframe.conversation import add_turns_task
from mindframe.models import LLM, Conversation, CustomUser, Intervention, Memory, Note, Turn
from mindframe.silly import silly_name
from mindframe.tree import conversation_history

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


class ConversationDetailView(LoginRequiredMixin, DetailView):
    model = Turn
    template_name = "conversation_detail.html"
    context_object_name = "session"
    slug_field = "uuid"
    slug_url_kwarg = "uuid"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["object"] = self.object.conversation

        tip_ = self.object.get_descendants().last()
        leaf_turn = tip_ or self.object
        turns = conversation_history(leaf_turn)

        context["turns"] = turns.prefetch_related(
            "speaker",
            "notes",
        )
        context["leaf_node"] = leaf_turn

        context["visible_turn_ids"] = turns.values_list("id", flat=True)
        context["branches"] = set(
            [i.get_parent() for i in self.object.conversation.turns.filter(branch=True)]
        )
        context["leaves"] = self.object.conversation.turns.filter(lft=F("rgt") - 1)

        context["root"] = self.object.conversation.turns.all().first().get_root()

        return context
