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
from django.conf import settings
from collections import OrderedDict

logger = logging.getLogger(__name__)

from magentic import OpenaiChatModel

from magentic.chat_model.litellm_chat_model import LitellmChatModel

from mindframe.multipart_llm import chatter
from mindframe.structured_judgements import (
    data_extraction_function_factory
    # pydantic_model_from_schema,
)

from mindframe.return_type_models import JUDGEMENT_RETURN_TYPES


def format_turns(turns):
    return "\n".join([f"{t.speaker.role.upper()}: {t.text}" for t in turns])



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
    """Each Step is a node in the intervention graph.
    
    This model handles the immediate response to the client in each turn.
    """

    intervention = models.ForeignKey(
        Intervention, on_delete=models.CASCADE, related_name="steps"
    )
    
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    prompt_template = models.TextField()

    
    def spoken_response(self, session) -> OrderedDict:
        """Use an llm to create a spoken response to clients, 
        using features of the session as context."""

        print("TURNS SO FAR:")
        print("\n\n---\n\n".join(session.turns.all().values_list('text', flat=True)))

        template = Template(self.prompt_template)
        context = Context(
            {
                "turns": format_turns(session.turns.all()),
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
        print(f"PROMPT:\n{pmpt}")
        completions = chatter(pmpt, model=settings.MINDFRAME_AI_MODELS.cheap)
        
        # returns an OrderedDict of completions (intermediate 'thougts' and the __RESPONSE__)
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
    conditions = models.JSONField(default=dict)

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
    pydantic_model_name = models.CharField(choices = [(k, k) for k, v in JUDGEMENT_RETURN_TYPES.items()], max_length=255, default='BriefNote')

    def pydantic_model(self):
        return JUDGEMENT_RETURN_TYPES[self.pydantic_model_name]

    # schema = models.JSONField(
    #     default={
    #         "properties": {"text": {"title": "Text", "type": "string"}},
    #         "required": ["text"],
    #         "title": "BriefNote",
    #         "type": "object",
    #     }
    # )

    def __str__(self):
        return f"{self.title}"# \n\n{self.schema}"


class Judgement(models.Model):
    intervention = models.ForeignKey("mindframe.Intervention", 
                                     on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    variable_name = models.CharField(max_length=255)
    prompt_template = models.TextField()
    return_type = models.ForeignKey(JudgementReturnType, on_delete=models.PROTECT)

    def __str__(self) -> str:
        return f"{self.title} ({self.variable_name})"
    
    def make_judgement(self, session):
        logger.debug(f"Making judgement {self.title} for {session}")
        template = Template(self.prompt_template)
        # extract this so DRY with Step.spoken_response
        context = Context(
            {
                "turns": format_turns(session.turns.all()),
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
            self.return_type.pydantic_model(),
            # remember, that other templating goes on prior, when generating {input}
            # these templates are stored in Judgement model instances in the db
            # this just adds the instruction to respond in JSON which is what we almost always want.
            prompt_template="{input}\nYou MUST use the tool calling functionality and respond in JSON in the correct format.",
        )

        newnote = Note.objects.create(judgement=self, session=session, inputs=inputs)
        with settings.MINDFRAME_AI_MODELS.cheap:
            llm_result = extraction_function(**newnote.inputs)
            newnote.data = llm_result.model_dump()
        
        print(f"JUDGEMENT RESULT: {llm_result}")
        
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
        turn = Turn.objects.create(session=self, speaker=speaker, text=text)
        turn.save()
        print(f"TURN SAVED: {turn}")
        return turn

    def respond(self):
        """Generate a response to the client's last utterance"""
        bot = CustomUser.objects.filter(role=RoleChoices.BOT).first()
        step = self.current_step()

        # make any required judgements first
        # these are defined by the possible transitions from the current step
        transitions = step.transitions_from.all()
        
        judgements_to_run = Judgement.objects.filter(pk__in=transitions.values("judgements"))
        logger.debug(f"JUDGEMENTS TO RUN: {judgements_to_run}")
        judgement_notes = []
        for judgement in judgements_to_run:
            judgement_notes.append(judgement.make_judgement(self))


        session_notes = self.notes.filter(data__response__isnull=False)
        "\n\n".join(map(str, session_notes.values('data')))

        # make a dictionary of the most recent note for each structured variable
        notes_with_variables = dict(session_notes.filter(data__response__isnull=False).order_by('judgement__variable_name', '-timestamp').distinct('judgement__variable_name').values_list('judgement__variable_name', 'data__response'))
        
        # now, decide if we should move to the next step or stay here
        # if conditions for a transition are met, then move to that step and make a
        # new TreatmentSessionState instance
        
        # TODO - THE LOGIC HERE IS VERY BRITTLE AND NEEDS SOME THOUGHT
        # CONSIDER THE CASE WHERE CONDITIONS NEED TO BE AND-ED TOGETHER
        # ALSO THERE MAY BE EDGE CASES WHERE MULTIPLE TRANSITIONS COULD BE PERMITTED
        # IN WHICH CASE WE SHOULD CHOOSE HOW???
        exitflag = False
        for t in transitions:
            if exitflag:
                break
            for c in t.conditions:
                if exitflag:
                    break
                # this is ANY condition, not ALL
                try:
                    passes_conditon = eval(c, {}, notes_with_variables)
                except Exception as e:
                    passes_conditon = False
                    logger.debug(f"CONDITION FAILED: {c}")

                if passes_conditon:
                    print(f"PASSED CONDIITON: {c} so changing state")
                    newstate = TreatmentSessionState.objects.create(
                        session=self, previous_step=step, step=t.to_step
                    )
                    print(f"SAVED PROGRESS/STATE: {newstate}")
                    
                    # update this for code below to know where we are
                    step = t.to_step
                    newstate.save()
                    exitflag = True
                    break


        # finally, generate a response to the client
        completions = step.spoken_response(self)
        key, utterance = next(reversed(completions.items()))
        # import pdb; pdb.set_trace()
        # save the turn containing the response
        newturn = Turn.objects.create(
            session=self, speaker=bot, 
            text=utterance.value, 
            metadata={k: i.json() for k, i in completions.items()}
        )
        newturn.save()

        
        # return the response only (this gets used by the gradio app)
        # perhaps we should return the Turn object and allow the gradio app to 
        # use other attributes of it?
        return utterance.value

    class Meta:
        ordering = ["-started"]

    def __str__(self):
        return f"<{self.pk}> Session on {self.started} for {self.cycle.client.username} in Cycle {self.cycle.id}"


class TreatmentSessionState(models.Model):
    '''Tracks state within a session: which step we are at, and have come from.'''

    session = models.ForeignKey(
        TreatmentSession, on_delete=models.CASCADE, related_name="progress"
    )
    timestamp = models.DateTimeField(default=timezone.now)
    previous_step = models.ForeignKey(
        Step,
        on_delete=models.CASCADE,
        related_name="progressions_from",
        null=True,
        blank=True,
    )
    step = models.ForeignKey(
        Step, on_delete=models.CASCADE, 
    )

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        return f"{self.previous_step} --> {self.step}"


class Turn(models.Model):
    """An individual utterance during a session (either client or therapist)."""

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
    """Clinical records created by exercuting a Judgement at a point in time"""

    session = models.ForeignKey(
        TreatmentSession, on_delete=models.CASCADE, related_name="notes"
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
        return self.data.get('text', None) or self.data
    
    def __str__(self):
        return f"Note made at {self.timestamp}"
