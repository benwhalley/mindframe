import logging
import re
from collections import defaultdict, OrderedDict
from enum import Enum

import shortuuid
from autoslug import AutoSlugField
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Count, Q
from django.template import Context, Template
from django.utils import timezone
from django.utils.text import slugify
from pydantic import BaseModel

logger = logging.getLogger(__name__)

import shortuuid
from magentic import OpenaiChatModel

from magentic.chat_model.litellm_chat_model import LitellmChatModel

# 24 chars in alphapbet and 22 long = 24^22 so still very large for guessing but easier to read for humans
shortuuid.set_alphabet("abcdefghjkmnpqrstuvwxyz")

from mindframe.multipart_llm import chatter

from mindframe.return_type_models import JUDGEMENT_RETURN_TYPES
from mindframe.structured_judgements import (
    data_extraction_function_factory,
    # pydantic_model_from_schema,
)


class RoleChoices(models.TextChoices):
    SYSTEM_DEVELOPER = "system_developer", "System Developer"
    INTERVENTION_DEVELOPER = "intervention_developer", "Intervention Developer"
    CLIENT = "client", "Client"
    SUPERVISOR = "supervisor", "Supervisor"
    BOT = "bot", "Bot"


class StepJudgementFrequencyChoices(models.TextChoices):
    TURN = "turn", "Each turn"
    ENTER = "enter", "When entering the step"
    EXIT = "exit", "When exiting the step"


def generate_short_uuid():
    return shortuuid.uuid().lower()


def format_turns(turns):
    return "\n".join([f"{t.speaker.role.upper()}: {t.text}" for t in turns.order_by("timestamp")])


class CustomUser(AbstractUser):

    role = models.CharField(
        max_length=30, choices=RoleChoices.choices, default=RoleChoices.CLIENT.value
    )

    def __str__(self):
        return self.username


class Intervention(models.Model):
    """A treatment intervention

    e.g. CBT or Functional Imagery Training"""

    def natural_key(self):
        return slugify(self.short_title)

    title = models.CharField(max_length=255)
    short_title = models.CharField(max_length=20)
    slug = AutoSlugField(populate_from="short_title", unique=True)

    response_format_instructions = models.TextField(
        help_text="Instructions for the bot on how to format it's response. Best done as a markdown list. Can be included as {{intervention.response_format_instructions}} in the prompt template.",
        default="""- respond in a single sentence\n""",
    )

    def __str__(self):
        return self.title

    class Meta:
        unique_together = ("title",)  # "version")


class Example(models.Model):

    intervention = models.ForeignKey(
        Intervention, on_delete=models.CASCADE, related_name="examples"
    )
    title = models.CharField(max_length=255)
    text = models.TextField()

    class Meta:
        unique_together = [("intervention", "title")]

    def __str__(self):
        return self.title


class StepJudgement(models.Model):
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

    def natural_key(self):
        return (
            slugify(self.judgement.title),
            slugify(self.step.title),
        )

    class Meta:

        unique_together = [("judgement", "step", "when")]


class Step(models.Model):
    """Each Step is a node in the intervention graph.

    This model handles the immediate response to the client in each turn.
    """

    def natural_key(self):
        return slugify(f"{self.intervention.title}__{self.title}")

    intervention = models.ForeignKey(Intervention, on_delete=models.CASCADE, related_name="steps")

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    prompt_template = models.TextField()
    judgements = models.ManyToManyField("Judgement", through="StepJudgement")

    def get_step_context(self, session):

        all_notes = Note.objects.filter(session_state__session__cycle=session.cycle)
        all_turns = Turn.objects.filter(session_state__session__cycle=session.cycle)

        context = Context(
            {
                "session": session,
                "intervention": session.cycle.intervention,
                # "examples": session.cycle.intervention.examples.all(),
                # just for this step
                "turns": format_turns(
                    all_turns.filter(session_state__session=session).filter(
                        session_state__step=self
                    )
                ),
                "session_turns": format_turns(all_turns.filter(session_state__session=session)),
                "all_turns": format_turns(all_turns),
                # just for this step -- note, this is done a different way than for turns
                "notes": all_notes.filter(session_state__session=session).filter(
                    timestamp__gt=session.progress.last().timestamp
                ),
                "session_notes": all_notes.filter(session_state__session=session),
                "all_notes": all_notes,
            }
        )
        return context

    def spoken_response(self, session) -> OrderedDict:
        """Use an llm to create a spoken response to clients,
        using features of the session as context."""

        template = Template(self.prompt_template)
        context = self.get_step_context(session)

        pmpt = template.render(context)
        # logger.info(f"PROMPT:\n{pmpt}")
        completions = chatter(pmpt, model=settings.MINDFRAME_AI_MODELS.expensive)

        # returns an OrderedDict of completions (intermediate 'thougts' and the __RESPONSE__)
        return completions

    class Meta:
        unique_together = [("intervention", "title"), ("intervention", "slug")]

    def __str__(self):
        return f"{self.title} ({self.intervention.title})"


class Transition(models.Model):
    """An edge between two Step nodes"""

    from_step = models.ForeignKey(Step, on_delete=models.CASCADE, related_name="transitions_from")
    to_step = models.ForeignKey(Step, on_delete=models.CASCADE, related_name="transitions_to")

    conditions = models.TextField(
        blank=True,
        help_text="Python code to evaluate before the transition can be be made. Each line is evaluated indendently and all must be True for the transition to be made. Variables created by Judgements are passed in as a dictionary.",
    )

    def clean(self):
        if self.from_step.intervention != self.to_step.intervention:
            raise ValidationError("from_step and to_step must belong to the same intervention.")

    def __str__(self):
        return f"{self.from_step} -> {self.to_step}"


class Judgement(models.Model):
    def natural_key(self):
        return slugify(f"{self.variable_name}")

    intervention = models.ForeignKey("mindframe.Intervention", on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    variable_name = models.CharField(max_length=255)
    prompt_template = models.TextField()
    pydantic_model_name = models.CharField(
        choices=[(k, k) for k, v in JUDGEMENT_RETURN_TYPES.items()],
        max_length=255,
        default="BriefNote",
    )
    valid_options = models.JSONField(default=list, blank=True, null=True)

    def return_type(self) -> BaseModel:
        cls_or_function = JUDGEMENT_RETURN_TYPES[self.pydantic_model_name]
        if self.valid_options:
            return cls_or_function(self.valid_options)
        return cls_or_function

    def __str__(self) -> str:
        return f"<{self.variable_name}> {self.title}"

    def make_judgement(self, session):
        logger.debug(f"Making judgement {self.title} for {session}")
        template = Template(self.prompt_template)
        # extract this so DRY with Step.spoken_response
        context = session.current_step().get_step_context(session)
        inputs = {"input": template.render(context)}
        try:
            return self.process_inputs(session, inputs)
        except Exception as e:

            # {'error': {'message': "The response was filtered due to the prompt triggering Azure OpenAI's content management policy. Please modify your prompt and retry. To learn more about our content filtering policies please read our documentation: https://go.microsoft.com/fwlink/?linkid=2198766", 'type': None, 'param': 'prompt', 'code': 'content_filter', 'status': 400, 'innererror': {'code': 'ResponsibleAIPolicyViolation',
            # TODO this was an error generated by OpenAI. We need to find a way of logging this type of error and handling it better. Also we need to warn the treatment developer that their prompt is triggering the content filter.

            logger.error(f"Error calling LLM: {e}")
            logger.error(f"Prompt: {inputs}")
            return None

    def process_inputs(self, session, inputs: dict):

        extraction_function = data_extraction_function_factory(
            self.return_type(),
            # remember, that other templating goes on prior, when generating {input}
            # these templates are stored in Judgement model instances in the db
            # this just adds the instruction to respond in JSON which is what we almost always want.
            prompt_template="{input}\nYou MUST use the tool calling functionality and respond in JSON in the correct format.",
        )

        newnote = Note.objects.create(
            judgement=self, session_state=session.progress.last(), inputs=inputs
        )
        with settings.MINDFRAME_AI_MODELS.expensive:
            llm_result = extraction_function(**newnote.inputs)
            newnote.data = llm_result.model_dump()

        logger.info(f"JUDGEMENT RESULT: {llm_result}")
        logger.warning(f"NEW NOTE: {newnote}")

        newnote.save()
        return newnote


# Records made at runtime


class Cycle(models.Model):
    """An Cycle of treatment linking multiple TreatmentSessions"""

    client = models.ForeignKey(CustomUser, on_delete=models.PROTECT, related_name="cycles")
    intervention = models.ForeignKey(
        "mindframe.Intervention", on_delete=models.PROTECT, related_name="Cycles"
    )
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.client} started {self.intervention.short_title}, {self.start_date}"


class TreatmentSession(models.Model):
    """An individual session in which a client uses the service"""

    def natural_key(self):
        return self.uuid

    uuid = models.CharField(unique=True, default=generate_short_uuid, editable=False, null=False)

    cycle = models.ForeignKey(Cycle, on_delete=models.CASCADE, related_name="sessions")
    started = models.DateTimeField(default=timezone.now)
    last_updated = models.DateTimeField(auto_now=True)

    @property
    def turns(self):
        return self.state().turns

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
        return self.state().step

    def listen(self, speaker, text):
        """Record a Turn in the session when the client speaks"""
        turn = Turn.objects.create(session_state=self.state(), speaker=speaker, text=text)
        turn.save()
        logger.info(f"TURN SAVED: {turn}")
        return turn

    def get_judgements_to_run(self, step, judgements):
        # find all the judgements that should be run on every turn
        potential_judgements_to_run = Judgement.objects.filter(
            pk__in=(judgements.values_list("judgement", flat=True))
        ).annotate(
            notes_count=Count(
                "note",
                filter=Q(note__session_state__session__cycle=self.cycle)
                & ~Q(note__data__value=None),
            )
        )

        # exclude ones where we already have a note and we only want to run once
        judgements_to_run = potential_judgements_to_run.exclude(
            stepjudgements__once=True, notes_count__gt=0
        )
        # log which ones we skipped
        for i in potential_judgements_to_run.filter(stepjudgements__once=True, notes_count__gt=0):
            nts = Note.objects.filter(judgement=i, session_state__session__cycle=self.cycle).values(
                "data"
            )
            logger.debug(f"SKIPPED JUDGEMENT: {i} - Existing Notes: {nts}")

        return judgements_to_run

    def build_client_data_dict(self, step):
        """Make a dictionary of the MOST RECENT note for each judgement variable plus metadata"""
        session_notes = Note.objects.filter(session_state__session=self).filter(data__isnull=False)
        client_data = defaultdict(lambda: None)
        client_data.update(
            dict(
                session_notes.order_by("judgement__variable_name", "-timestamp").distinct(
                    "judgement__variable_name"
                )
                # data__value is a magic field name - see return_type_models.py
                .values_list("judgement__variable_name", "data__value")
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

    def evaluate_transitions_and_update_step(self, step, transitions, client_data):
        # check each of the conditions for each transition, line by line
        # all of the conditions must hold for the transition to be made
        # conditions are evaluated in a clean context with no globals but
        # do have access to the client_data default dictionary (default=None)

        # TODO: helping users debug their conditions and providing sensible error
        # messages will be important here and needs to be added.
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
            jvals_ = [j.make_judgement(self) for j in judgements_to_run]

            step = next_step  # Update the step to reflect the new state

        return step

    def respond(self):
        """Respond to the client's last utterance (and manage transitions)."""

        bot = CustomUser.objects.filter(role=RoleChoices.BOT).first()
        step = self.current_step()
        transitions = step.transitions_from.all()

        # for now, just get all the judgements that are run on every turn
        turn_jgmnts = step.stepjudgements.filter(when=StepJudgementFrequencyChoices.TURN)
        judgements_to_run = self.get_judgements_to_run(step, turn_jgmnts)

        # do the judgements we need now
        jvals_ = [j.make_judgement(self) for j in judgements_to_run]

        client_data = self.build_client_data_dict(step)

        step = self.evaluate_transitions_and_update_step(step, transitions, client_data)

        # generate a response using the current or newly updated step
        completions = step.spoken_response(self)
        key, utterance = next(reversed(completions.items()))

        # save the generated response as a new Turn
        newturn = Turn.objects.create(
            session_state=self.state(),
            speaker=bot,
            text=utterance.value,
            metadata={k: i.json() for k, i in completions.items()},
        )
        newturn.save()

        # return the response only (this gets used by the gradio app)
        # perhaps we should return the Turn object and allow the gradio app to
        # use other attributes of it?
        logger.warning(utterance.value)
        return utterance.value

    class Meta:
        ordering = ["-started"]

    def __str__(self):
        return f"<{self.pk}> Session on {self.started} for {self.cycle.client.username} in Cycle {self.cycle.id}"


class TreatmentSessionState(models.Model):
    """Tracks state within a session: which step we are at, and have come from."""

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

    uuid = models.CharField(unique=True, default=generate_short_uuid, editable=False, null=False)

    session_state = models.ForeignKey(
        TreatmentSessionState,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="turns",
    )

    timestamp = models.DateTimeField(default=timezone.now)
    speaker = models.ForeignKey(CustomUser, on_delete=models.PROTECT, null=False, blank=False)
    text = models.TextField(blank=True, null=True)

    metadata = models.JSONField(
        blank=True,
        null=True,
        help_text="Additional data like preparation, hidden tokens, LLM call chains etc.",
    )

    def __str__(self):
        return f"{self.speaker.get_full_name().upper()} ({self.timestamp}): {self.text}"


class Note(models.Model):
    """Clinical records created by exercuting a Judgement at a point in time"""

    uuid = models.CharField(unique=True, default=generate_short_uuid, editable=False, null=False)

    session_state = models.ForeignKey(
        TreatmentSessionState,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notes",
    )

    judgement = models.ForeignKey(Judgement, on_delete=models.PROTECT)
    timestamp = models.DateTimeField(default=timezone.now)

    inputs = models.JSONField(default=dict, null=True, blank=True)
    # for clinical Note type records, save a 'text' key
    # for other return types, save multiple string keys
    # type of this values is Dict[str, str | int]
    # todo? add some validatio?
    data = models.JSONField(default=dict, null=True, blank=True)

    def val(self):
        return self.data.get("text", None) or self.data

    def __str__(self):
        return f"{self.judgement.return_type} made at {self.timestamp}"
