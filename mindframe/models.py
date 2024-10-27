import re
from enum import Enum

from magentic.chat_model.litellm_chat_model import LitellmChatModel
from magentic import OpenaiChatModel

from autoslug import AutoSlugField
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from magentic import OpenaiChatModel

from mindframe.multipart_llm import chatter



free = LitellmChatModel("ollama_chat/llama3.2", api_base="http://localhost:11434")
expensive=OpenaiChatModel("gpt-4o")
cheap=OpenaiChatModel("gpt-4o-mini")


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
        unique_together = ("title", ) #"version")


class Example(models.Model):
    intervention = models.ForeignKey(Intervention, on_delete=models.CASCADE)
    title= models.CharField(max_length=255)
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
        # returns and OrderedDict of completions (thougts and response)
        history = "\n".join([f"{i.speaker}: {i.text}" for i in session.turns.all()])
        pmpt = self.prompt_template.format(history=history)
        completions =  chatter(pmpt, model=expensive)
        tht = completions.get("THOUGHTS", None)
        print(tht and tht.value or "???")
        return  completions
    
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

    conditions = models.JSONField(default={})

    def clean(self):
        if self.from_step.intervention != self.to_step.intervention:
            raise ValidationError(
                "from_step and to_step must belong to the same intervention."
            )

    def __str__(self):
        return f"{self.from_step} -> {self.to_step}"


class Judgement(models.Model):
    intervention = models.ForeignKey("mindframe.Intervention", on_delete=models.CASCADE)
    prompt_template = models.TextField()
    return_type = models.JSONField(default={}, help_text="A serialised PyDantic object")


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
        return f"{self.client} started {self.intervention.short_title}, {self.start_date}"


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
                session=self, 
                to_step=self.cycle.intervention.steps.first()
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
        completions = step.think_and_respond(self)
        
        key, utterance =  next(reversed(completions.items()))
        newturn = Turn.objects.create(session=self, 
                                      speaker=bot, 
                                      text=utterance.value, 
                                      metadata=completions)
        newturn.save()
        return utterance.value

    class Meta:
        ordering = ["-started"]

    def __str__(self):
        return f"Session on {self.started} for {self.cycle.client.username} in Cycle {self.cycle.id}"


class Progress(models.Model):
    session = models.ForeignKey(
        TreatmentSession, on_delete=models.CASCADE, related_name="progress"
    )
    timestamp = models.DateTimeField(default=timezone.now)
    from_step = models.ForeignKey(
        Step, on_delete=models.CASCADE, related_name="progress_from", null=True, blank=True
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

    # for clinical Note type records, save a 'text' key
    # for other return types, save multiple string keys
    # type of this values is Dict[str, str | int]
    # todo? add some validatio?
    data = models.JSONField(default={})

    def __str__(self):
        return f"Note by made at {self.timestamp}"
