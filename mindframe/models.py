import os
import hashlib
import json
import logging
from collections import defaultdict, OrderedDict
from box import Box

from enum import Enum, auto
from django.forms.models import model_to_dict

import shortuuid
from autoslug import AutoSlugField
from django.conf import settings
from django.utils.safestring import mark_safe
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.db import models
from django.db.models import Count, Q


from django.template import Context, Template
from django.utils import timezone
from django.utils.text import slugify
from pydantic import BaseModel
from pgvector.django import VectorField, HnswIndex
import shortuuid
from django_lifecycle import LifecycleModel, hook, AFTER_UPDATE

import instructor


# use langfuse for tracing
# TODO: currently broken because doesn't report audio_tokens in usage properly
# from langfuse.openai import AzureOpenAI, OpenAI
from openai import AzureOpenAI, OpenAI

from django.db.models import Model
from langfuse.decorators import langfuse_context

langfuse_context.configure(debug=False)
from langfuse.decorators import observe

from mindframe.llm_calling import chatter, structured_chat
from mindframe.settings import MINDFRAME_SHORTUUID_ALPHABET

from mindframe.tasks import generate_embedding


logger = logging.getLogger(__name__)

shortuuid.set_alphabet(MINDFRAME_SHORTUUID_ALPHABET)


def s_uuid():
    return shortuuid.uuid()


class RoleChoices(models.TextChoices):
    """Defines various roles in the system such as developers, clients, and supervisors."""

    SYSTEM_DEVELOPER = "system_developer", "System Developer"
    INTERVENTION_DEVELOPER = "intervention_developer", "Intervention Developer"
    CLIENT = "client", "Client"
    SUPERVISOR = "supervisor", "Supervisor"
    THERAPIST = "therapist", "Therapist"


class StepJudgementFrequencyChoices(models.TextChoices):
    """Specifies when/how frequently a judgement should be made during a step."""

    TURN = "turn", "Each turn"
    ENTER = "enter", "When entering the step"
    EXIT = "exit", "When exiting the step"


class CustomUser(AbstractUser):
    """Custom user model with additional role field for defining user roles."""

    role = models.CharField(
        max_length=30, choices=RoleChoices.choices, default=RoleChoices.CLIENT.value
    )

    def __str__(self):
        return self.username


class Intervention(LifecycleModel):
    """A treatment/intervention, including steps, transitions, and related metadata."""

    def natural_key(self):
        return slugify(self.short_title)

    def compute_version(self):
        """Compute a version hash based on all linked objects."""

        hashed_fields = {
            "interventions": [
                "title",
            ],  # "short_title"],
            "steps": ["title", "prompt_template"],
            "transitions": ["conditions"],  # "from_step__title", "to_step__title",
            "judgements": [
                "title",
            ],  # "variable_name", "prompt_template"],
            "examples": ["title", "text"],
        }

        related_data = {
            "intervention": model_to_dict(self, fields=hashed_fields["interventions"]),
            "steps": list(self.steps.values(*hashed_fields["steps"])),
            "transitions": list(
                Transition.objects.filter(from_step__intervention=self).values(
                    *hashed_fields["transitions"]
                )
            ),
            "judgements": list(
                Judgement.objects.filter(intervention=self).values(*hashed_fields["judgements"])
            ),
            "examples": list(self.examples.values(*hashed_fields["examples"])),
        }
        serialized_data = json.dumps(related_data, sort_keys=True)
        print(serialized_data)
        return hashlib.sha256(serialized_data.encode("utf-8")).hexdigest()

    @hook(AFTER_UPDATE)
    def update_version(self, *args, **kwargs):
        new_version = self.compute_version()
        if self.version != new_version:
            # Prevent recursive save
            self.version = new_version
            super(Intervention, self).save(update_fields=["version"])

    def get_export_url(self):
        return reverse("admin:mindframe_export", args=[self.id])

    title = models.CharField(max_length=255)
    short_title = models.CharField(max_length=20)
    slug = AutoSlugField(populate_from="short_title", unique=True)
    version = models.CharField(max_length=64, null=True, editable=False)
    sem_ver = models.CharField(max_length=64, null=True, editable=True)

    # TODO - make this non nullable
    default_conversation_model = models.ForeignKey(
        "LLM",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="default_for_conversations",
    )
    default_judgement_model = models.ForeignKey(
        "LLM",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="default_for_judgements",
    )

    def transitions(self):
        return Transition.objects.filter(
            Q(from_step__intervention=self) | Q(to_step__intervention=self)
        )

    def ver(self):
        return self.version and self.version[:8] or "-"

    def __str__(self):
        return f"{self.title} ({self.sem_ver}/{self.ver()})"

    class Meta:
        unique_together = ("title", "version", "sem_ver")


class Example(LifecycleModel):
    """Stores examples related to Interventions, including embeddings for vector search."""

    intervention = models.ForeignKey(
        Intervention, on_delete=models.CASCADE, related_name="examples"
    )
    title = models.CharField(max_length=255)
    text = models.TextField()

    # embedding = VectorField(dimensions=384, null=True, blank=True)

    # class Meta:
    #     indexes = [
    #         HnswIndex(
    #             name="example_embedding_index",
    #             fields=["embedding"],
    #             m=16,
    #             ef_construction=64,
    #             opclasses=["vector_l2_ops"],
    #         ),
    #     ]

    @hook(AFTER_UPDATE)
    def on_text_change(self):
        return generate_embedding.delay(self.pk)

        unique_together = [("intervention", "title")]

    def __str__(self):
        return self.title


class StepJudgement(models.Model):
    """Relationships between steps and judgements, and when a Judgement should be made."""

    judgement = models.ForeignKey(
        "Judgement", related_name="stepjudgements", on_delete=models.CASCADE
    )
    step = models.ForeignKey("Step", related_name="stepjudgements", on_delete=models.CASCADE)
    when = models.CharField(
        choices=StepJudgementFrequencyChoices.choices,
        default=StepJudgementFrequencyChoices.TURN,
        max_length=10,
    )
    once = models.BooleanField(
        default=False, help_text="Once we have a non-null value returned, don't repeat."
    )
    use_as_guidance = models.BooleanField(
        default=False,
        help_text="Allow this judgement to be used as guidance when generating responses to the client. Exposed as a list of {{guidance}} in the prompt template.",
    )

    def natural_key(self):
        return (
            slugify(self.judgement.title),
            slugify(self.step.title),
        )

    class Meta:

        unique_together = [("judgement", "step", "when")]


class Step(models.Model):
    """Represents a step in an intervention, including a prompt template and Judgements."""

    def natural_key(self):
        return slugify(f"{self.intervention.title}__{self.title}")

    intervention = models.ForeignKey(Intervention, on_delete=models.CASCADE, related_name="steps")

    title = models.CharField(max_length=255)
    slug = AutoSlugField(populate_from="title")
    prompt_template = models.TextField()
    judgements = models.ManyToManyField("Judgement", through="StepJudgement")

    def get_absolute_url(self):
        return reverse("admin:mindframe_step_change", args=[str(self.id)])

    def make_data_variable(self, session):
        """This makes the `data` context variable, used in the prompt template.

        The layout/structure of this object is important because end-users will access it in templates and it needs to be consistent/predictable and provide good defaults.
        """

        def getv(notes, v):
            notes = notes.filter(judgement__variable_name=v)
            r = {v: notes.last().data, v + "__all": notes}
            return r

        # get all notes for this session and flatten them so that we can access the latest
        # instance of each Judgement/Note by variable name
        notes = Note.objects.filter(turn__session_state__session__cycle=session.cycle)
        vars = set(notes.values_list("judgement__variable_name", flat=True))
        dd = {}
        for i in vars:
            dd.update(getv(notes, i))

        return dd

    def get_step_context(self, session) -> dict:

        all_notes = Note.objects.filter(turn__session_state__session__cycle=session.cycle)
        all_turns = Turn.objects.filter(session_state__session__cycle=session.cycle)

        # ALI - THIS IS AN IMPORTANT PART BECAUSE IT PROVIDES CONTEXT FOR THE LLM WHEN RESPONDING TO CLIENTS AND ALSO WHEN MAKING JUDGEMENTS
        # FOR SOME THINGS WE WILL BE ABLE TO EXTEND THIS FUNCTION AND PROVIDE MORE CONTEXT
        # IN OTHER CASES (E.G. FOR RAG) WE WILL NEED TO MAKE A TEMPLATETAG AND USE THAT IN THE PROMPT TEMPLATE TO DYNAMICALLY EXTRACT EXTRA CONTEXT

        context = {
            "session": session,
            "intervention": session.cycle.intervention,
            "notes": all_notes.filter(turn__session_state__session=session).filter(
                timestamp__gt=session.state.timestamp
            ),
            "session_notes": all_notes.filter(turn__session_state__session=session),
            "all_notes": all_notes,
            "data": self.make_data_variable(session),
        }
        return context

    def get_model(self, session):
        return session.cycle.intervention.default_conversation_model

    @observe(capture_input=False, capture_output=False)
    def spoken_response(self, turn) -> OrderedDict:
        """Use an llm to create a spoken response to clients, using session data as context."""

        langfuse_context.update_current_observation(
            name=f"Response ({self})",
        )

        session = turn.session_state.session
        ctx = self.get_step_context(session)

        completions, llm_calls = chatter(
            self.prompt_template,
            context=ctx,
            model=self.get_model(session),
            log_context={
                "step": self,
                "session": session,
                "prompt": self.prompt_template,
                "turn": turn,
                "context": ctx,
            },
        )
        # returns an OrderedDict of completions (intermediate 'thougts' and the RESPONSE_)
        return completions, llm_calls

    class Meta:
        unique_together = [("intervention", "title"), ("intervention", "slug")]

    def __str__(self):
        return f"{self.title} ({self.intervention.title}, {self.intervention.sem_ver}/{self.intervention.ver()})"


class Transition(models.Model):
    """A transition between Steps, specifying required conditions to be met."""

    from_step = models.ForeignKey(Step, on_delete=models.CASCADE, related_name="transitions_from")
    to_step = models.ForeignKey(Step, on_delete=models.CASCADE, related_name="transitions_to")

    conditions = models.TextField(
        blank=True,
        help_text="Python code to evaluate before the transition can be be made. Each line is evaluated indendently and all must be True for the transition to be made. Variables created by Judgements are passed in as a dictionary.",
    )

    def clean(self):
        if self.from_step.intervention != self.to_step.intervention:
            raise ValidationError("from_step and to_step must belong to the same intervention.")

    class Meta:
        unique_together = [("from_step", "to_step", "conditions")]

    def __str__(self):
        return f"{self.from_step} -> {self.to_step}"


class Judgement(models.Model):
    """A Judgement to be made on the current session state.

        Judgements are defined by a prompt template and expected return type/acceptable return values.

    jj =Judgement.objects.last()
    ss = TreatmentSession.objects.last()
    tt = ss.turns.all().last()
    jr = jj.make_judgement(tt)
    jr.items()
    """

    def natural_key(self):
        return slugify(f"{self.variable_name}")

    intervention = models.ForeignKey("mindframe.Intervention", on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    slug = AutoSlugField(populate_from="title")
    variable_name = models.CharField(max_length=255)
    task_summary = models.TextField(
        blank=True,
        null=True,
        help_text="A brief summary of the task or question asked by this judgement. E.g. 'Evaluate the client's emotional state'.",
    )
    prompt_template = models.TextField()

    @observe(capture_input=False, capture_output=False)
    def make_judgement(self, turn):
        """

        s = TreatmentSession.objects.last()
        self = Judgement.objects.first()
        self.make_judgement(s)
        """
        langfuse_context.update_current_observation(name=f"Judgement: {self}")

        session = turn.session_state.session
        logger.debug(f"Making judgement {self.title} for {session}")
        try:
            return self.process_inputs(
                turn, inputs=session.current_step().get_step_context(session)
            )
        except Exception as e:
            raise e
            logger.error(f"ERROR MAKING JUDGEMENT {e}")
            return None

    def get_model(self, session):
        return session.cycle.intervention.default_conversation_model

    def process_inputs(self, turn, inputs: dict):

        newnote = Note.objects.create(judgement=self, turn=turn, inputs=None)
        session = turn.session_state.session

        llm_result, logs = chatter(
            self.prompt_template,
            model=self.get_model(session),
            context=inputs,
            log_context={"judgement": self, "session": session, "inputs": inputs, "turn": turn},
        )

        newnote.data = llm_result
        newnote.save()
        return newnote

    def __str__(self) -> str:
        return f"<{self.variable_name}> {self.title} ({self.intervention.short_title} {self.intervention.sem_ver})"

    class Meta:
        unique_together = [("intervention", "title"), ("intervention", "slug")]


# ######################### #
#
#
# Records made at runtime


class Cycle(models.Model):
    """A cycle of treatment for a client, linking multiple treatment sessions."""

    client = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="cycles")
    intervention = models.ForeignKey(
        "mindframe.Intervention", on_delete=models.CASCADE, related_name="Cycles"
    )
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.client} started {self.intervention.short_title}, {self.start_date}"


class TreatmentSession(models.Model):
    """An individual 'session' for a client within a treatment cycle."""

    def natural_key(self):
        return self.uuid

    uuid = models.CharField(unique=True, default=s_uuid, editable=False, null=False)
    cycle = models.ForeignKey(Cycle, on_delete=models.CASCADE, related_name="sessions")
    started = models.DateTimeField(default=timezone.now)
    last_updated = models.DateTimeField(auto_now=True)

    def chatbot_link(self):
        return f"{settings.CHAT_URL}/?session_id={self.uuid}"

    @property
    def turns(self):
        return self.state.turns

    @property
    def state(self):
        # the state of the TreatmentSession is defined by TreatmentSessionState records (the last one represents our current position in the intervention)
        prg = self.progress.all()
        if prg.count() > 0:
            # return the step of the last progress record (i.e. the current step)
            return self.progress.last()
        else:
            # if there are no progress records, create one so we know we're on the first step
            p_ = TreatmentSessionState.objects.create(
                session=self, step=self.cycle.intervention.steps.first()
            )
            p_.save()
            return p_

    def current_step(self):
        return self.state.step

    def listen(self, speaker, text, timestamp=None):
        """Record a Turn in the session when the client speaks"""
        timestamp = timestamp or timezone.now()

        turn = Turn.objects.create(
            session_state=self.state, speaker=speaker, text=text, timestamp=timestamp
        )
        turn.save()
        logger.info(f"TURN SAVED: {turn}")
        return turn

    def get_judgements_to_run(self, step, judgements):
        # find all the judgements that should be run on every turn
        potential_judgements_to_run = Judgement.objects.filter(
            pk__in=(judgements.values_list("judgement", flat=True))
        ).annotate(
            notes_count=Count(
                "notes",
                filter=Q(notes__turn__session_state__session__cycle=self.cycle)
                & ~Q(notes__data__value=None),
            )
        )

        # exclude ones where we already have a note and we only want to run once
        judgements_to_run = potential_judgements_to_run.exclude(
            stepjudgements__once=True, notes_count__gt=0
        )
        # log which ones we skipped
        for i in potential_judgements_to_run.filter(stepjudgements__once=True, notes_count__gt=0):
            nts = Note.objects.filter(
                judgement=i, turn__session_state__session__cycle=self.cycle
            ).values("data")
            logger.debug(f"SKIPPED JUDGEMENT: {i} - Existing Notes: {nts}")

        return judgements_to_run

    def build_client_data_dict(self, step):
        """Make a dictionary of the MOST RECENT note for each judgement variable plus metadata"""
        session_notes = Note.objects.filter(turn__session_state__session=self).filter(
            data__isnull=False
        )
        client_data = defaultdict(lambda: None)
        client_data.update(
            dict(
                session_notes.order_by("judgement__variable_name", "-timestamp").distinct(
                    "judgement__variable_name"
                )
                # `data`` can contain multiple values, each defined by a different completion - see return_type_models.py
                .values_list("judgement__variable_name", "data")
            )
        )

        # add metadata to this dict to use as context in evaluating transition conditions
        client_data.update(
            {
                "n_turns_step": self.turns.filter(session_state__step=step).count(),
                "n_turns_session": self.turns.filter().count(),
            }
        )
        logger.debug(f"DATA DETERMINING TRANSITION: {client_data}")
        return client_data

    def evaluate_transitions_and_update_step(self, turn, step, transitions, client_data):
        # check each of the conditions for each transition, line by line
        # all of the conditions must hold for the transition to be made
        # conditions are evaluated in a clean context with no globals but
        # do have access to the client_data default dictionary (default=None)

        # TODO: helping users debug their conditions and providing sensible error
        # messages will be important here and needs to be added.

        # convert to a dotten namespace to allowed dotted access to vars in conditions users write
        # from box import Box
        # x=Box({'a': {'c':3}, 'b': 2}, default_box=True)
        # eval("x.a.c", {}, x) == x.a.c
        # eval("a.a.c", {}, x) == x.a.c

        client_data = Box(client_data, default_box=True)
        logger.debug(f"CLIENT DATA AS BOX: {client_data}")
        transition_results = [
            (
                t,
                [
                    (c, eval(c, {}, client_data))
                    for c in list(map(str.strip, filter(bool, t.conditions.split("\n"))))
                ],
            )
            for t in transitions
        ]

        transition_results = [(i, all([r for c, r in l]), l) for i, l in transition_results]
        logger.debug(f"TRANSITION RESULTS: {transition_results}")

        # Find transitions that passed (if any)
        next_step = None
        valid_transitions = [t for t, passed, l in transition_results if passed]
        if valid_transitions:
            # for now, just pick the first transition that passed
            next_step = transitions[0].to_step
            newstate = TreatmentSessionState.objects.create(
                session=self, previous_step=step, step=next_step
            )
            newstate.save()

            # do any extra judgements needed
            step_jgm_enter_exit = StepJudgement.objects.filter(
                Q(
                    pk__in=next_step.stepjudgements.filter(
                        when=StepJudgementFrequencyChoices.ENTER
                    ).values("pk")
                )
                | Q(
                    pk__in=step.stepjudgements.filter(
                        when=StepJudgementFrequencyChoices.EXIT
                    ).values("pk")
                )
            )

            judgements_to_run = self.get_judgements_to_run(step, step_jgm_enter_exit)
            logger.debug(f"ENTRY/EXIT JUDGEMENTS TO RUN: {judgements_to_run}")

            # then do the judgements we need
            jvals_ = [j.make_judgement(turn) for j in judgements_to_run]

            step = next_step  # Update the step to reflect the new state

        return step

    @observe(capture_input=False, capture_output=True)
    def respond(self):
        """Respond to the client's last utterance (and manage transitions)."""

        langfuse_context.update_current_observation(
            name=f"Respond: {self.state}", session_id=self.uuid
        )

        bot = CustomUser.objects.filter(role=RoleChoices.THERAPIST).first()
        if not bot:
            raise Exception("No therapist user found to respond to client.")

        step = self.current_step()
        transitions = step.transitions_from.all()

        # for now, just get all the judgements that are run on every turn
        turn_jgmnts = step.stepjudgements.filter(when=StepJudgementFrequencyChoices.TURN)
        judgements_to_run = self.get_judgements_to_run(step, turn_jgmnts)

        # generate a new turn for the bot
        newturn = Turn.objects.create(speaker=bot, session_state=self.state)
        newturn.save()

        # do the judgements we need now
        jvals_ = [j.make_judgement(newturn) for j in judgements_to_run]

        client_data = self.build_client_data_dict(step)

        step = self.evaluate_transitions_and_update_step(newturn, step, transitions, client_data)

        completions, llm_logs = step.spoken_response(newturn)

        # the final completion is the response to return
        key, utterance = next(reversed(completions.items()))

        # save the generated response and other data to the new Turn
        newturn.session_state = self.state  # update in case we changed step
        newturn.text = utterance
        newturn.metadata = dict(completions.items())
        newturn.save()

        # return the response only (this gets used by the gradio app)
        # perhaps we should return the Turn object and allow the gradio app to
        # use other attributes of it?
        return utterance

    def get_absolute_url(self):
        return reverse("treatment_session_detail", args=[str(self.uuid)])

    class Meta:
        ordering = ["-started"]

    def __str__(self):
        return f"<{self.pk}> Session on {self.started} for {self.cycle.client.username} in Cycle {self.cycle.id}"


class TreatmentSessionState(models.Model):
    """Tracks the state of a treatment session, including the current and previous steps."""

    session = models.ForeignKey(TreatmentSession, on_delete=models.CASCADE, related_name="progress")
    timestamp = models.DateTimeField(default=timezone.now)
    previous_step = models.ForeignKey(
        Step,
        on_delete=models.CASCADE,
        related_name="progressions_from",
        null=True,
        blank=True,
    )
    step = models.ForeignKey(
        Step,
        on_delete=models.CASCADE,
    )

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        return f"{self.step.title}"


class Turn(models.Model):
    """An individual utterance during a session (either client or therapist)."""

    uuid = models.CharField(unique=True, default=s_uuid, editable=False, null=False)

    session_state = models.ForeignKey(
        TreatmentSessionState,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="turns",
    )

    timestamp = models.DateTimeField(default=timezone.now)
    speaker = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=False, blank=False)
    text = models.TextField(blank=True, null=True)

    metadata = models.JSONField(
        blank=True,
        null=True,
        help_text="Additional data like preparation, hidden tokens, LLM call chains etc.",
    )

    def __str__(self):
        return f"{self.speaker.get_full_name().upper()} ({self.timestamp}): {self.text}"


class Note(models.Model):
    """Stores clinical records or outputs from Judgements made during treatment sessions.

    Notes can be either plain text or contasin structured data, depending on the Judgement that created them.
    """

    uuid = models.CharField(unique=True, default=s_uuid, editable=False, null=False)

    # session_state = models.ForeignKey(
    #     TreatmentSessionState,
    #     on_delete=models.CASCADE,
    #     null=True,
    #     blank=True,
    #     related_name="notes",
    # )

    turn = models.ForeignKey(
        "Turn",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notes",
    )

    judgement = models.ForeignKey(Judgement, on_delete=models.CASCADE, related_name="notes")
    timestamp = models.DateTimeField(default=timezone.now)

    inputs = models.JSONField(default=dict, null=True, blank=True)
    # for clinical Note type records, save a 'text' key
    # for other return types, save multiple string keys
    # type of this values is Dict[str, str | int]
    # todo? add some validatio?
    data = models.JSONField(default=dict, null=True, blank=True)

    def val(self):
        return (
            self.data.get("text", None) or {"task_summary": self.judgement.task_summary} | self.data
        )

    def __str__(self):
        return (
            f"[{self.judgement.variable_name}] made {self.timestamp.strftime('%d %b %Y, %-I:%M')}"
        )


class LLMLogTypes(models.TextChoices):
    """Types of logs that can be stored in the LLMLog model."""

    ERROR = auto()
    USAGE = auto()


class LLMLog(models.Model):
    """Log LLM usage and errors."""

    timestamp = models.DateTimeField(default=timezone.now)
    log_type = models.CharField(
        choices=LLMLogTypes.choices, max_length=25, default=LLMLogTypes.USAGE
    )
    step = models.ForeignKey(Step, on_delete=models.CASCADE, null=True, blank=True)
    judgement = models.ForeignKey(Judgement, on_delete=models.CASCADE, null=True, blank=True)
    model = models.ForeignKey("LLM", on_delete=models.CASCADE, null=True, blank=True)

    session = models.ForeignKey(TreatmentSession, on_delete=models.CASCADE, null=True, blank=True)
    turn = models.ForeignKey(
        Turn, on_delete=models.CASCADE, null=True, blank=True, related_name="llm_calls"
    )

    message = models.TextField(blank=True, null=True)
    prompt_text = models.TextField(blank=True, null=True)
    metadata = models.JSONField(default=dict, null=True, blank=True)

    def __str__(self):
        return f"<{self.pk}> {self.timestamp}: {self.message}"


class SyntheticConversation(models.Model):
    """A synthetic conversation between two TreatmentSessions"""

    session_one = models.ForeignKey(
        TreatmentSession, on_delete=models.CASCADE, related_name="conversation_one"
    )
    session_two = models.ForeignKey(
        TreatmentSession, on_delete=models.CASCADE, related_name="conversation_two"
    )
    start_time = models.DateTimeField(default=timezone.now)

    def get_absolute_url(self):
        return reverse("fake_conversation_detail", args=[str(self.pk)])

    def __str__(self):
        return f"Synthetic conversation between Session {self.session_one.id} and Session {self.session_two.id} starting at {self.start_time}"


class LLMProvider(models.TextChoices):
    AZURE = auto()
    OLLAMA = auto()


class LLM(models.Model):
    """Store details of Language Models used for Step and Judgement execution"""

    model_name = models.CharField(
        max_length=255, help_text="Litellm model name, e.g. ollama/llama3.2 or azure/gpt-4o"
    )

    def __str__(self) -> str:
        return self.model_name

    @property
    def provider(self):
        # this is an Azure instance, but is used to query litellm proxy
        return instructor.from_openai(AzureOpenAI())
