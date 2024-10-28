import re
from enum import Enum

from autoslug import AutoSlugField
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.template import Context, Template
from django.utils import timezone
from django.utils.text import slugify
import logging

logger = logging.getLogger(__name__)

from magentic import OpenaiChatModel

from magentic.chat_model.litellm_chat_model import LitellmChatModel

from mindframe.multipart_llm import chatter
from mindframe.structured_judgements import (
    data_extraction_function_factory,
    pydantic_model_from_schema,
)


free = LitellmChatModel("ollama_chat/llama3.2", api_base="http://localhost:11434")
expensive = OpenaiChatModel("gpt-4o")
cheap = OpenaiChatModel("gpt-4o-mini")


class RoleChoices(models.TextChoices):
    SYSTEM_DEVELOPER = "system_developer", "System Developer"
    INTERVENTION_DEVELOPER = "intervention_developer", "Intervention Developer"
    CLIENT = "client", "Client"
    SUPERVISOR = "supervisor", "Supervisor"
    BOT = "bot", "Bot"


class CustomUser(AbstractUser):

    role = models.CharField(
        max_length=30, choices=RoleChoices.choices, default=RoleChoices.CLIENT.value
    )

    def __str__(self):
        return self.username


class Intervention(models.Model):
    """A treatment intervention

    e.g. CBT or Functional Imagery Training"""

    title = models.CharField(max_length=255)
    short_title = models.CharField(max_length=20)
    # version = models.CharField(max_length=50, blank=True)

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

    def __str__(self):
        return self.title


class Step(models.Model):
    """Each Step is a node in the intervention graph"""

    intervention = models.ForeignKey(
        Intervention, on_delete=models.CASCADE, related_name="steps"
    )
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    prompt_template = models.TextField()

    def think_and_respond(self, session):
        # returns an OrderedDict of completions (thougts and response)
        template = Template(self.prompt_template)
        context = Context(
            {
                "turns": session.turns.all(),
                "session": session,
                "examples": session.cycle.intervention.examples.all(),
                "session_notes": session.notes.all(),
                "cycle_notes": Note.objects.filter(
                    session__cycle=session.cycle
                ).exclude(session=session),
                "notes": Note.objects.filter(session__cycle=session.cycle),
            }
        )
        pmpt = template.render(context)
        completions = chatter(pmpt, model=cheap)
        tht = completions.get("THOUGHTS", None)
        rsp = completions.get("RESPONSE", None)
        print(tht and tht.value or "???")
        print(rsp and rsp.value.upper() or "???")
        return completions

    class Meta:
        unique_together = [("intervention", "title"), ("intervention", "slug")]

    def __str__(self):
        return f"{self.title} ({self.intervention.title})"


class Transition(models.Model):
    """An edge between two Step nodes"""

    from_step = models.ForeignKey(
        Step, on_delete=models.CASCADE, related_name="transitions_from"
    )
    to_step = models.ForeignKey(
        Step, on_delete=models.CASCADE, related_name="transitions_to"
    )

    judgements = models.ManyToManyField("Judgement", related_name="transitions")
    conditions = models.JSONField(default={})

    def clean(self):
        if self.from_step.intervention != self.to_step.intervention:
            raise ValidationError(
                "from_step and to_step must belong to the same intervention."
            )

    def __str__(self):
        return f"{self.from_step} -> {self.to_step}"


class JudgementReturnType(models.Model):
    """A serialised Pydantic object representing the return type of a Judgement"""

    title = models.CharField(max_length=255)
    schema = models.JSONField(
        default={
            "properties": {"text": {"title": "Text", "type": "string"}},
            "required": ["text"],
            "title": "BriefNote",
            "type": "object",
        }
    )

    def __str__(self):
        return f"{self.title}"# \n\n{self.schema}"


class Judgement(models.Model):
    intervention = models.ForeignKey("mindframe.Intervention", on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    prompt_template = models.TextField()
    return_type = models.ForeignKey(JudgementReturnType, on_delete=models.PROTECT)

    def make_judgement(self, session):
        logger.debug(f"Making judgement {self.title} for {session}")
        template = Template(self.prompt_template)
        # extract this so DRY with Step.think_and_respond
        context = Context(
            {
                "turns": session.turns.all(),
                "session": session,
                "examples": session.cycle.intervention.examples.all(),
                "session_notes": session.notes.all(),
                "cycle_notes": Note.objects.filter(
                    session__cycle=session.cycle
                ).exclude(session=session),
                "notes": Note.objects.filter(session__cycle=session.cycle),
            }
        )
        inputs = {'input': template.render(context)}
        return self.process_inputs(session, inputs)

    def process_inputs(self, session, inputs: dict):

        extraction_function = data_extraction_function_factory(
            pydantic_model_from_schema(self.return_type.schema),
            # remember, that other templating goes on prior, when generating {input}
            # these templates are stored in Judgement model instances in the db
            # this just adds the instruction to respond in JSON which is what we almost always want.
            prompt_template="{input}\nRespond in JSON",
        )

        newnote = Note.objects.create(judgement=self, session=session, inputs=inputs)
        newnote.data = extraction_function(**newnote.inputs).model_dump()
        newnote.save()
        return newnote

    def __str__(self):
        return f"{self.title}"


# Records made at runtime


class Cycle(models.Model):
    """An Cycle of treatment linking multiple TreatmentSessions"""

    client = models.ForeignKey(
        CustomUser, on_delete=models.PROTECT, related_name="Cycles"
    )
    intervention = models.ForeignKey(
        "mindframe.Intervention", on_delete=models.PROTECT, related_name="Cycles"
    )
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return (
            f"{self.client} started {self.intervention.short_title}, {self.start_date}"
        )


class TreatmentSession(models.Model):
    """An individual session in which a client uses the service"""

    cycle = models.ForeignKey(Cycle, on_delete=models.CASCADE, related_name="sessions")
    started = models.DateTimeField(default=timezone.now)
    last_updated = models.DateTimeField(auto_now=True)

    def current_step(self):
        prg = self.progress.all()
        if prg.count() > 0:
            return self.progress.last().to_step
        else:
            p_ = Progress.objects.create(
                session=self, to_step=self.cycle.intervention.steps.first()
            )
            p_.save()
            return p_.to_step

    def listen(self, speaker, text):
        turn = Turn.objects.create(session=self, speaker=speaker, text=text)
        turn.save()
        return turn

    def respond(self):

        bot = CustomUser.objects.filter(role=RoleChoices.BOT).first()
        step = self.current_step()

        # make required judgements first
        judgements_to_run = Judgement.objects.filter(pk__in=step.transitions_from.all().values
        ("judgements"))
        logger.debug(f"JUDGEMENTS TO RUN: {judgements_to_run}")
        judgement_notes = []
        for judgement in judgements_to_run:
            judgement_notes.append(judgement.make_judgement(self))

        print(judgement_notes)

        completions = step.think_and_respond(self)

        key, utterance = next(reversed(completions.items()))
        newturn = Turn.objects.create(
            session=self, speaker=bot, text=utterance.value, metadata=completions
        )
        newturn.save()
        return utterance.value

    class Meta:
        ordering = ["-started"]

    def __str__(self):
        return f"<{self.pk}> Session on {self.started} for {self.cycle.client.username} in Cycle {self.cycle.id}"


class Progress(models.Model):
    session = models.ForeignKey(
        TreatmentSession, on_delete=models.CASCADE, related_name="progress"
    )
    timestamp = models.DateTimeField(default=timezone.now)
    from_step = models.ForeignKey(
        Step,
        on_delete=models.CASCADE,
        related_name="progress_from",
        null=True,
        blank=True,
    )
    to_step = models.ForeignKey(
        Step, on_delete=models.CASCADE, related_name="progress_to"
    )

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        return f"{self.from_step} --> {self.to_step}"


class Turn(models.Model):
    """An individual utterance during a session"""

    session = models.ForeignKey(
        TreatmentSession, on_delete=models.CASCADE, related_name="turns"
    )
    timestamp = models.DateTimeField(default=timezone.now)
    speaker = models.ForeignKey(
        CustomUser, on_delete=models.PROTECT, null=False, blank=False
    )
    text = models.TextField(blank=True, null=True)

    metadata = models.JSONField(
        blank=True,
        null=True,
        help_text="Additional data like preparation, hidden tokens, LLM call chains etc.",
    )

    def __str__(self):
        return f"{self.speaker.get_full_name().upper()} ({self.timestamp}): {self.text}"


class Note(models.Model):
    """Notes, preferences and other records created by Judgements during a TreatmentSession"""

    session = models.ForeignKey(
        TreatmentSession, on_delete=models.CASCADE, related_name="notes"
    )
    judgement = models.ForeignKey(Judgement, on_delete=models.PROTECT)
    timestamp = models.DateTimeField(default=timezone.now)

    inputs = models.JSONField(default={}, null=True, blank=True)
    # for clinical Note type records, save a 'text' key
    # for other return types, save multiple string keys
    # type of this values is Dict[str, str | int]
    # todo? add some validatio?
    data = models.JSONField(default={}, null=True, blank=True)

    def val(self):
        return self.data.get('text', None) or self.data
    
    def __str__(self):
        return f"Note made at {self.timestamp}"
