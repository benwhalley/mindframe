import logging
import random
from itertools import cycle

from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic.detail import DetailView
from django.views.generic.edit import FormMixin, FormView

from mindframe.conversation import continue_conversation_task, listen
from mindframe.models import Conversation, CustomUser, Intervention, Step, Turn
from mindframe.settings import InterventionTypes
from mindframe.silly import silly_user
from mindframe.tree import (
    conversation_history,
    generate_d3_tree_data,
    generate_mermaid_tree,
    generate_treant_tree_data,
)

logger = logging.getLogger(__name__)


class AdditionalTurnsForm(forms.Form):
    n_turns = forms.IntegerField(
        label="Number of Turns",
        min_value=1,
        max_value=100,
        initial=2,
        help_text="Specify how many additional turns to generate.",
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )

    next_speaker_step = forms.ModelChoiceField(
        required=True,
        queryset=Step.objects.all(),
        help_text=f"Select an intervention/step for the next speaker ",
    )
    subsequent_speaker_step = forms.ModelChoiceField(
        required=True,
        queryset=Step.objects.all(),
        help_text=f"Select an intervention/step for the subsequent speaker ",
    )


class ConversationDetailView(LoginRequiredMixin, DetailView, FormMixin):
    model = Turn
    template_name = "conversation_detail.html"
    context_object_name = "session"
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    form_class = AdditionalTurnsForm
    to_leaf = False

    def get_success_url(self):
        return reverse("conversation_detail", kwargs={"uuid": self.object.uuid})

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            n_turns = form.cleaned_data["n_turns"]

            # if the user only added 1 turn there is only 1 speaker/user created at
            # this point so we need to create a second to allow conversation to continue
            # `additional_speaker` is the key for the unknown speaker in the AdditionalTurnsForm

            self.object.conversation.synthetic_turns_scheduled += n_turns
            self.object.conversation.save()

            subsequent_speaker = self.object.speaker
            next_speaker = (
                self.object.conversation.speakers().exclude(pk=subsequent_speaker.pk).first()
                or silly_user()
            )

            speakers_steps = [
                (next_speaker.pk, form.cleaned_data["next_speaker_step"].pk),
                (
                    subsequent_speaker.pk,
                    form.cleaned_data["subsequent_speaker_step"].pk,
                ),
            ]
            continue_conversation_task.delay(
                from_turn_id=self.object.pk,
                speakers_steps=speakers_steps,
                n_turns=n_turns,
            )

            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def get_form_kwargs(self):
        """Pass the conversation instance to the form dynamically."""
        kwargs = super().get_form_kwargs()
        # kwargs["conversation"] = self.object.conversation
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = self.get_form()

        context["turn"] = self.object
        context["object"] = self.object.conversation
        # deepest leaf node on this branch
        leaf_node = self.object.get_descendants().order_by("-depth", "-rgt").first() or self.object

        turns = conversation_history(self.object, to_leaf=self.to_leaf)

        context["turns"] = turns.prefetch_related(
            "speaker",
            "notes",
        )
        context["leaf_node"] = leaf_node

        context["visible_turn_ids"] = turns.values_list("id", flat=True)
        context["branches"] = set(
            [i.get_parent() for i in self.object.conversation.turns.filter(branch=True)]
        )
        context["leaves"] = self.object.conversation.turns.filter(lft=F("rgt") - 1)

        context["root"] = self.object.conversation.turns.all().first().get_root()

        return context


class ImportConversationForm(forms.Form):
    therapist_first = forms.BooleanField(
        required=False,
        initial=True,
        help_text="Therapist speaks first. Deselect if the client speaks first.",
    )
    transcript = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 10, "cols": 80}),
        initial="Hi, welcome to the session. Do you have any questions about Mindframe?",
        help_text="Paste conversation transcript, one row per speaker. Splits on line breaks and assumes client/therapist alternate turns.",
    )
    synthetic_client = forms.ModelChoiceField(
        required=False,
        queryset=Intervention.objects.filter(intervention_type=InterventionTypes.CLIENT),
        help_text="Optionally select an existing client intervention",
    )
    synthetic_therapist = forms.ModelChoiceField(
        required=False,
        queryset=Intervention.objects.filter(intervention_type=InterventionTypes.THERAPY),
        help_text="Optionally select an existing therapist intervention",
    )

    # client = forms.ModelChoiceField(
    #     queryset=CustomUser.objects.none(),
    #     required=False,
    #     help_text="Optionally select an existing client user",
    # )

    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)
    #     if Intervention.objects.exists():
    #         self.fields["therapist"].queryset = CustomUser.objects.filter(role="therapist")
    #         self.fields["therapist"].initial = CustomUser.objects.filter(role="therapist").first()

    #         self.fields["therapist"].queryset = CustomUser.objects.filter(role="client")


class ImportConversationView(LoginRequiredMixin, FormView):
    template_name = "import_conversation_form.html"
    form_class = ImportConversationForm
    success_url = reverse_lazy("conversation_detail")

    def form_valid(self, form):
        transcript = [i.strip() for i in form.cleaned_data["transcript"].split("\n")]
        # therapist = form.cleaned_data["therapist"]
        # client = form.cleaned_data["client"]

        # Create users if not provided
        # if not therapist:
        therapist = CustomUser.objects.create(
            username=f"therapist_{random.randint(1000, 9999)}", role="therapist"
        )
        # if not client:
        client = CustomUser.objects.create(
            username=f"client_{random.randint(1000, 9999)}", role="client"
        )

        conversation = Conversation.objects.create()
        conversation.synthetic_client = form.cleaned_data["synthetic_client"]
        conversation.synthetic_therapist = form.cleaned_data["synthetic_therapist"]
        conversation.save()

        speakers_ = (
            form.cleaned_data["therapist_first"] and [therapist, client] or [client, therapist]
        )
        speakers = cycle(speakers_)
        lines = zip(transcript, speakers)

        # add the root node
        firstline, firstspeaker = lines.__next__()
        turn = Turn.add_root(conversation=conversation, speaker=firstspeaker, text=firstline)
        for line, spkr in lines:
            turn = listen(turn, line, spkr)

        return redirect(reverse_lazy("conversation_detail", kwargs={"uuid": turn.uuid}))


class ConversationMermaidView(DetailView):
    model = Conversation
    template_name = "conversation_mermaid.html"
    context_object_name = "conversation"
    slug_field = "uuid"
    slug_url_kwarg = "uuid"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        conversation = self.object  # Retrieved Conversation instance
        root_turn = conversation.turns.get(depth=1)  # Assuming root turn has depth=1
        context["mermaid_code"] = generate_mermaid_tree(root_turn)
        context["tree_data"] = generate_treant_tree_data(root_turn)
        return context
