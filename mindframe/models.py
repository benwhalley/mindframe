import hashlib
import json
import logging
from datetime import timedelta
from itertools import groupby

import dateparser
import instructor
import shortuuid
from autoslug import AutoSlugField
from box import Box
from dateutil import rrule
from decouple import config
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, OuterRef, Q, QuerySet, Subquery, Window
from django.db.models.functions import RowNumber
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.forms.models import model_to_dict
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django_lifecycle import AFTER_CREATE, AFTER_UPDATE, LifecycleModel, hook
from langfuse.decorators import langfuse_context, observe

# use langfuse for tracing
from langfuse.openai import OpenAI
from pgvector.django import HnswIndex, L2Distance, VectorField
from recurrent.event_parser import RecurringEvent
from treebeard.ns_tree import NS_Node

from llmtools.llm_calling import chatter, get_embedding, simple_chat
from mindframe.chunking import CHUNKER_TEMPLATE
from mindframe.settings import (
    DEFAULT_CHUNKING_MODEL_NAME,
    DEFAULT_CONVERSATION_MODEL_NAME,
    DEFAULT_JUDGEMENT_MODEL_NAME,
    MINDFRAME_SHORTUUID_ALPHABET,
    BranchReasons,
    InterventionTypes,
    RoleChoices,
    StepJudgementFrequencyChoices,
    TurnTextSourceTypes,
)
from mindframe.shortuuidfield import MFShortUUIDField as ShortUUIDField
from mindframe.tree import iter_conversation_path

logger = logging.getLogger(__name__)
langfuse_context.configure(debug=False)
shortuuid.set_alphabet(MINDFRAME_SHORTUUID_ALPHABET)


# ################################################ #
#
#
# Model instances which configure the system
# (not necessarily at runtime, for those see below)


class Intervention(LifecycleModel):
    """
    An intervention or treatment: a definition of the conversation content and structure.

    Interventions connect Steps, Judgements, Transitions, and related metadata.
    """

    def compute_version(self) -> str:
        """Compute a version hash based on all linked objects."""

        hashed_fields = {
            "interventions": [
                "title",
            ],
            "steps": ["prompt_template"],
            "transitions": ["conditions"],  # "from_step__title", "to_step__title",
            "judgements": [
                "variable_name",
                "prompt_template",
            ],
            "memories": ["text"],
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
            "memories": list(self.memories.all().values(*hashed_fields["memories"])),
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
    slug = AutoSlugField(populate_from="title", unique=True, editable=True, always_update=False)
    version = models.CharField(max_length=64, null=True, editable=False)
    sem_ver = models.CharField(max_length=64, null=True, editable=True)

    intervention_type = models.CharField(
        choices=InterventionTypes.choices, default=InterventionTypes.THERAPY, max_length=30
    )

    default_speaker = models.ForeignKey(
        "CustomUser",
        help_text="The default speaker for this intervention (e.g. if used in a synthetic conversation)",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="default_for_interventions",
    )

    def get_default_speaker(self):
        # todo: make a client user if it's a client intervention
        if self.default_speaker:
            return self.default_speaker
        else:
            s, _ = CustomUser.objects.get_or_create(
                username="therapist",
                defaults={"role": "therapist", "email": "therapist@example.com"},
            )
            return s

    is_default_intervention = models.BooleanField(default=False)

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

    default_chunking_model = models.ForeignKey(
        "LLM",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="default_for_chunking",
    )

    def transitions(self) -> QuerySet["Transition"]:
        return Transition.objects.filter(
            Q(from_step__intervention=self) | Q(to_step__intervention=self)
        )

    def ver(self):
        return self.version and self.version[:8] or "-"

    def natural_key(self) -> str:
        return slugify(self.title)

    def __str__(self):
        return f"{self.title} ({self.sem_ver}/{self.ver()})"

    class Meta:
        unique_together = ("title", "version", "sem_ver")


class StepJudgement(models.Model):
    """
    M2M through model for Steps and Judgements, says _when_ a Judgement should be made
    """

    judgement = models.ForeignKey(
        "Judgement", related_name="stepjudgements", on_delete=models.CASCADE
    )
    step = models.ForeignKey("Step", related_name="stepjudgements", on_delete=models.CASCADE)

    when = models.CharField(
        choices=StepJudgementFrequencyChoices.choices,
        default=StepJudgementFrequencyChoices.TURN,
        max_length=10,
    )

    n_turns = models.PositiveSmallIntegerField(
        blank=True, null=True, help_text="If run by-turn, run the Judgement every N turns"
    )
    offline = models.BooleanField(
        default=False, help_text="Run this Judgement offline, outside the reply loop"
    )

    def clean(self):
        # note also the Meta index which enforces this constraint
        super().clean()
        if self.when == StepJudgementFrequencyChoices.TURN and (
            self.n_turns is None or self.n_turns < 1
        ):
            raise ValidationError({"n_turns": "n_turns must be at least 1 when 'when' is TURN."})

    once = models.BooleanField(
        default=False, help_text="Once we have a non-null value returned, don't repeat."
    )

    def natural_key(self):
        return (self.judgement.natural_key(), self.step.natural_key(), self.when)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(when=StepJudgementFrequencyChoices.TURN, n_turns__gte=1)
                | ~models.Q(when=StepJudgementFrequencyChoices.TURN),
                name="n_turns_must_be_positive_for_turn",
            )
        ]
        unique_together = [("judgement", "step", "when")]


class Step(models.Model):
    """
    Step in an intervention, instructions for how to respond

    `prompt_template` is an LLM instruction, specifying what to say.
    `judgements` are other prompts which need to be run before responding, to inform the response.

    """

    intervention = models.ForeignKey(Intervention, on_delete=models.CASCADE, related_name="steps")

    title = models.CharField(max_length=255)
    order = models.PositiveSmallIntegerField(default=1)
    slug = AutoSlugField(populate_from="title")
    judgements = models.ManyToManyField("Judgement", through="StepJudgement")

    opening_line = models.TextField(
        blank=True,
        verbose_name="Fixed opening line",
        null=True,
        help_text="Opening statement if no conversation history exists. E.g. 'How are you today? Leave blank to have the first line be generated by the prompt_template.'",
    )

    prompt_template = models.TextField()

    def get_absolute_url(self):
        return reverse("admin:mindframe_intervention_change", args=[str(self.intervention.id)])

    def natural_key(self):
        return (self.intervention.natural_key(), slugify(self.title))

    class Meta:
        unique_together = [("intervention", "title"), ("intervention", "slug")]
        ordering = ["intervention", "order", "title"]

    def __str__(self):
        return f"{self.title} | {self.intervention.title}"


class Transition(models.Model):
    """A transition between Steps, specifying required conditions to be met."""

    from_step = models.ForeignKey(Step, on_delete=models.CASCADE, related_name="transitions_from")
    to_step = models.ForeignKey(Step, on_delete=models.CASCADE, related_name="transitions_to")

    conditions = models.TextField(
        blank=True,
        help_text="Python code to evaluate before the transition can be be made. Each line is evaluated indendently and all must be True for the transition to be made. Variables created by Judgements are passed in as a dictionary.",
    )

    priority = models.PositiveSmallIntegerField(default=1)

    def clean(self):
        if self.from_step.intervention != self.to_step.intervention:
            raise ValidationError("from_step and to_step must belong to the same intervention.")

    def natural_key(self):
        return (self.from_step.natural_key(), self.to_step.natural_key(), self.conditions)

    class Meta:
        unique_together = [("from_step", "to_step", "conditions")]
        ordering = ["priority"]

    def __str__(self):
        return f"{self.from_step} -> {self.to_step}"


class Judgement(models.Model):
    """A Judgement to be made on the current Conversation state.

    Judgements are defined by a prompt template and expected return type/acceptable return values.
    """

    def natural_key(self):
        return slugify(f"{self.variable_name}")

    intervention = models.ForeignKey("mindframe.Intervention", on_delete=models.CASCADE)
    prompt_template = models.TextField()
    variable_name = AutoSlugField(
        editable=True,
        unique_with="intervention",
        max_length=255,
    )

    def __str__(self) -> str:
        return f"<{self.variable_name}> ({self.intervention.title} {self.intervention.sem_ver})"

    def natural_key(self):
        return (self.intervention.natural_key(), slugify(self.variable_name))

    class Meta:
        unique_together = [
            ("intervention", "variable_name"),
        ]


class LLMManager(models.Manager):
    def get_by_natural_key(
        self,
        model_name,
    ):
        return self.get(model_name=model_name)


class LLM(models.Model):
    """Store details of Language Models used for Step and Judgement execution"""

    objects = LLMManager()

    model_name = models.CharField(
        max_length=255, help_text="Litellm model name, e.g. llama3.2 or gpt-4o"
    )

    api_key = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Litellm API key, defaults to LITELLM_API_KEY",
    )
    base_url = models.CharField(
        max_length=1024,
        blank=True,
        null=True,
        help_text="Litellm base URL defaults to LITELLM_ENDPOINT",
    )

    def __str__(self) -> str:
        return self.model_name

    def chatter(self, prompt, context=None):
        from llmtools.llm_calling import chatter

        return chatter(prompt, self, context={}, log_context={})

    @property
    def client(self):
        # this is an Azure/OpenAI clent instance, but is used to query the litellm
        # proxy. It must provide chat.completions.create_with_completion and
        # client.chat.completions.create
        return instructor.from_openai(
            OpenAI(api_key=config("LITELLM_API_KEY"), base_url=config("LITELLM_ENDPOINT"))
        )

    def natural_key(self):
        return (self.model_name,)

    def get_by_natural_key(self, model_name):
        return self.get(model_name=model_name)

    class Meta:
        unique_together = [("model_name",)]


# ################################################ #
#
#
# Model instances created in runtime operation


class CustomUser(AbstractUser):
    """Custom user model with additional role field for defining user roles."""

    role = models.CharField(
        max_length=30, choices=RoleChoices.choices, default=RoleChoices.CLIENT.value
    )

    def transcript_speaker_label(self, intervention=None):
        # TODO: allow intervention to be passed to influence how transcripts
        # are presented to the mode. Could be either [client]/][therapist] or
        # real names/usernames
        return f"[{self.username}] "

    def natural_key(self):
        return (self.username,)

    class Meta:
        unique_together = [("username",)]

    def __str__(self):
        return self.username


class Note(models.Model):
    """
    Stores clinical records or outputs from Judgements made during Conversations

    Notes can be either plain text or contain structured data, depending on the
    Judgement that created them.
    """

    uuid = ShortUUIDField(max_length=len(shortuuid.uuid()) + 1, unique=True, editable=False)

    turn = models.ForeignKey(
        "Turn",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notes",
    )

    judgement = models.ForeignKey(Judgement, on_delete=models.CASCADE, related_name="notes")
    timestamp = models.DateTimeField(default=timezone.now)

    # for clinical Note type records, save a 'text' key
    # for other return types, save multiple string keys
    # type of this values is Dict[str, str | int]
    # todo? add some validatio?
    data = models.JSONField(default=dict, null=True, blank=True)

    class Meta:
        ordering = ["timestamp"]

    def val(self):
        return Box(self.data, default_box=True)

    def __str__(self):
        return (
            f"[{self.judgement.variable_name}] made {self.timestamp.strftime('%d %b %Y, %-I:%M')}"
        )


### QuerySet for MemoryChunk (Supports Chaining)
class MemoryChunkQuerySet(models.QuerySet):
    def search(self, query, method="semantic", llm=None, top_k=5):
        """
        Generalized search function supporting both HyDE and semantic search.

        Args:
            query (str): The input text query to search for.
            method (str): The search method, either "semantic" or "hyde".
            llm (LLM): The language model used for HyDE (ignored for semantic search).
            top_k (int): Number of closest matches to return.

        Returns:
            QuerySet: The top_k MemoryChunk objects closest to the query.
        """
        if method not in ["semantic", "hyde"]:
            raise ValueError(f"Invalid search method: {method}. Use 'semantic' or 'hyde'.")

        # Generate the embedding for semantic search
        if method == "semantic":
            query_embedding = get_embedding([query])[0]

        # Generate the hypothetical document for HyDE, then embed it
        elif method == "hyde":
            if not llm:
                raise ValueError("HyDE search requires an LLM instance.")
            hyde_prompt = f"""
            Imagine conversations between a therapist and client about {query}.
            Provide a concise imagined dialogue that captures key ideas and discussions.
            No more than 5 utterances.
            """
            hyde_completion = simple_chat(hyde_prompt, llm)[0]
            query_embedding = get_embedding([hyde_completion])[0]

        # Perform search using vector similarity
        return (
            self.alias(distance=L2Distance("embedding", query_embedding)).order_by("distance")[
                :top_k
            ],
            query,
            method == "hyde" and hyde_completion or None,
        )

    def windows(self, before=1, after=2):
        """
        Expands the queryset by including up to `before` chunks before and `after` chunks after each chunk.

        Args:
            before (int): Number of chunks before each chunk.
            after (int): Number of chunks after each chunk.

        Returns:
            QuerySet: Expanded queryset including all chunks in windows around the originals.
        """
        # Get distinct memory IDs in the queryset

        qs_ids = list(self.values_list("pk", flat=True))
        qs_mems = list(set(self.values_list("memory", flat=True)))
        memory_chunks = MemoryChunk.objects.filter(memory_id__in=qs_mems).annotate(
            rank=Window(
                expression=RowNumber(), partition_by=F("memory_id"), order_by=F("start").asc()
            )
        )

        desired_item_ranks = [
            (i.memory, list(range(i.rank - before, i.rank + after)))
            for i in memory_chunks
            if i.pk in qs_ids
        ]

        out = []
        for mem, rnks in desired_item_ranks:
            out.extend(memory_chunks.filter(memory=mem, rank__in=rnks).values_list("pk", flat=True))

        return memory_chunks.filter(pk__in=out).order_by("memory_id", "rank")

    def window_texts(self):
        """
        Groups contiguous MemoryChunks and returns their combined text.

        Returns:
            List[str]: A list of concatenated texts from contiguous MemoryChunks.
        """
        chunks = list(self.order_by("memory_id", "chunk_start"))

        grouped_texts = []
        for _, group in groupby(chunks, key=lambda c: c.memory_id):
            group = list(group)
            combined_texts = []
            buffer = [group[0].text]

            # Iterate through sorted chunks and merge contiguous ones
            for prev, current in zip(group, group[1:]):
                if prev.chunk_end == current.chunk_start:  # Contiguous
                    buffer.append(current.text)
                else:  # Discontinuous, start new grouping
                    combined_texts.append(" ".join(buffer))
                    buffer = [current.text]

            combined_texts.append(" ".join(buffer))
            grouped_texts.extend(combined_texts)

        return grouped_texts


### Custom Manager for MemoryChunk
class MemoryChunkManager(models.Manager):
    def get_queryset(self):
        return MemoryChunkQuerySet(self.model, using=self._db)


### MemoryChunk Model
class MemoryChunk(models.Model):
    memory = models.ForeignKey("Memory", on_delete=models.CASCADE, related_name="chunks")
    embedded_text = models.TextField(
        blank=True,
        null=True,
        help_text="The actual text embedded (may include extra tokens to contextualise/summarise passage to aid matching)",
    )
    start = models.IntegerField(help_text="The start position of the chunk in the memory (chars)")
    end = models.IntegerField(help_text="The end position of the chunk in the memory")
    embedding = VectorField(dimensions=1024, null=True, blank=True)

    objects = MemoryChunkManager()  # Use custom manager

    def __str__(self):
        return self.text

    @property
    def text(self):
        return self.memory.text[self.start : self.end]

    class Meta:
        indexes = [
            HnswIndex(
                name="embedding_index",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            )
        ]


### Memory QuerySet (For Searching Across Memories)
class MemoryQuerySet(models.QuerySet):
    def search(self, query, method="semantic", llm=None, top_k=5):
        """
        Allows Memory.objects.search() to return MemoryChunks matching the query.

        Args:
            query (str): The input text query to search for.
            method (str): The search method, either "semantic" or "hyde".
            llm (LLM): The language model used for HyDE (ignored for semantic search).
            top_k (int): Number of closest matches to return.

        Returns:
            QuerySet: A queryset of MemoryChunk objects that match the query.
        """
        return MemoryChunk.objects.filter(memory__in=self).search(
            query=query, method=method, llm=llm, top_k=top_k
        )


### Custom Manager for Memory
class MemoryManager(models.Manager):
    def get_queryset(self):
        return MemoryQuerySet(self.model, using=self._db)


class Memory(LifecycleModel):
    text = models.TextField()
    intervention = models.ForeignKey(
        "Intervention", on_delete=models.CASCADE, related_name="memories"
    )

    # TODO: decide, should this be on Conversation?
    turn = models.ForeignKey("Turn", blank=True, null=True, on_delete=models.CASCADE)

    objects = MemoryManager()  # Use custom manager

    def __str__(self):
        return self.text[:100]

    class Meta:
        verbose_name_plural = "Memories"

    @hook(AFTER_CREATE)
    @hook(AFTER_UPDATE)
    def make_chunks(self, method="llm"):
        self.chunks.all().delete()
        llm = self.intervention.default_chunking_model or LLM.objects.first()

        # Split text into lines and compute cumulative character offsets
        textlines = self.text.split("\n")
        line_start_positions = [0]  # First line always starts at character 0

        for line in textlines:
            line_start_positions.append(line_start_positions[-1] + len(line) + 1)  # +1 for '\n'

        # Generate chunks using the LLM chunking model
        numbered_text = "\n".join([f"{i+1}: {l}" for i, l in enumerate(textlines)])
        chunks = llm.chatter(CHUNKER_TEMPLATE.format(source=numbered_text)).response

        embedding_texts = []
        chunk_objects = []

        for i in chunks:
            # Convert line indices to character positions
            char_start = line_start_positions[i.start]
            char_end = (
                line_start_positions[i.end] if i.end < len(line_start_positions) else len(self.text)
            )

            # Extract text using character positions
            t_ = self.text[char_start:char_end]
            embtex = f"{i.description}\n\n{t_}"

            embedding_texts.append(embtex)
            chunk_objects.append(
                MemoryChunk(
                    memory=self,
                    start=char_start,  # Now in character positions
                    end=char_end,  # Now in character positions
                    embedded_text=embtex,
                )
            )

        # Batch process embeddings
        embeddings = get_embedding(embedding_texts)

        # Assign embeddings to chunk objects
        for chunk, embedding in zip(chunk_objects, embeddings):
            chunk.embedding = embedding

        MemoryChunk.objects.bulk_create(chunk_objects)

        return self.chunks.all()


class Conversation(LifecycleModel):
    """
    Store conversations as a Tree

    Why not a simple list? Because we will allow multiple branches from a given 'turn' in a conversation.  E.g.:

    - We simulate 'restarting' a conversation from a given point during testing
    - We test different scenarios for Step transitions... e.g. if we are generating synthetic conversations, we might want to transition between steps early or late, and see the effect on some metric/eval.
    - We allow for multiple hypothetical alternatives to a given turn, e.g. if we wanted to collate different experts compltions for the next best thing for the therapist to say, or humans role-playing different scenarios which the therapist has to follow through on.

    This setup would also allow for group conversations, even though we're not doing this right now.
    """

    uuid = ShortUUIDField(max_length=len(shortuuid.uuid()) + 1, editable=False)
    is_synthetic = models.BooleanField(default=False)
    archived = models.BooleanField(default=False)
    telegram_conversation_id = models.CharField(max_length=255, blank=True, null=True)

    synthetic_client = models.ForeignKey(
        "Intervention",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Default intervention to choose as a partner when creating a new Synthetic conversation turns",
    )
    synthetic_turns_scheduled = models.PositiveSmallIntegerField(default=0)

    def get_absolute_url(self):
        return settings.WEB_URL + reverse(
            "conversation_transcript",
            args=[
                self.turns.all().order_by("depth").last().uuid,
            ],
        )

    def __str__(self):
        return f"Conversation between: {', '.join(self.speakers().values_list('username', flat=True))} ()"

    def previous_turn_of_speaker(self, start_node, speaker):
        for node in iter_conversation_path(start_node, direction="up"):
            if node.speaker_id == speaker.id:
                return node
        return None

    def speakers(self) -> QuerySet["CustomUser"]:
        return CustomUser.objects.filter(
            id__in=Subquery(self.turns.values_list("speaker", flat=True).distinct())
        )

    def interventions(self):
        return self.turns.all().values_list("step__intervention", flat=True).distinct()


class Turn(NS_Node):
    """
    Represents a 'turn' in the conversation.

    Conversations are trees rather than lists. At each node in the tree
    we can branch into 'alternative' turns to simulate different scenarios
    or different lines of conversations.

    Nested sets (NS_Node) is chosen for read performance. Writes are not a
    concern because we're always appending at the branch tips and not moving
    stuff around much.
    """

    uuid = ShortUUIDField(max_length=len(shortuuid.uuid()) + 1, unique=True, editable=False)

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="turns")
    timestamp = models.DateTimeField(default=timezone.now)

    speaker = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="turns")

    # in some cases, we will create a hypothetical/counterfactual turn,
    # e.g. to simulate an alternative client or therapist response and
    # see how a conversation could progress differently from that point.
    # Another use would be to collate different expert predictions for
    # what _should_ be said at a given point, and compare these to the
    # original conversation line.
    branch = models.BooleanField(
        default=False,
        help_text="Is this a an alternative version of something that was said in the main conversation? I.e. was it used to create a branch in the conversation tree - perhaps to collate alternatives for a particular turn?",
    )

    branch_reason = models.CharField(
        choices=BranchReasons.choices, max_length=25, default=BranchReasons.MAIN
    )

    def gradio_url(self, request):
        from mindframe.views.general import start_gradio_chat

        return start_gradio_chat(request, turn_uuid=self.uuid).url

    branch_author = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="counterfactual_turns",
        null=True,
        blank=True,
    )

    step = models.ForeignKey(
        Step,
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        related_name="generated_turns",
        help_text="The Step used to generate this contribution to the conversation. If null, contributed by a human speaker.",
    )

    nudge = models.ForeignKey(
        "Nudge",
        help_text="The scheduled Nudge which generated this turn (if any)",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    text = models.TextField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True, null=True)
    text_source = models.CharField(
        choices=TurnTextSourceTypes.choices, max_length=25, default=TurnTextSourceTypes.HUMAN
    )

    embedding = VectorField(dimensions=1024, null=True, blank=True)

    # how sibling nodes are ordered within the same level
    # we do non-branches first, then by timestamp to enable
    # is to select the first sibling at each node as the 'real'
    # conversation path
    node_order_by = ["branch", "timestamp"]

    def notes_data(self):
        # Assumes Note has a ForeignKey to Turn with related_name="notes"
        return "\n".join(
            f"<{note.judgement.variable_name}>: {note.data}" for note in self.notes.all()
        )

    notes_data.short_description = "Notes Data"

    def get_absolute_url(self):
        return reverse("conversation_transcript", args=[self.uuid]) + "#turn-" + self.uuid

    def __str__(self):
        return f"{self.uuid}"


# class ChatInvite(LifecycleModel):
#     invitor = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="invites_sent")
#     invite_code = models.CharField(max_length=255, unique=True)
#     valid_until = models.DateTimeField(default=timezone.now+timezone.timedelta(months=1))

#     def telegram_deeplink(self):
#         from mindframe.settings import TELEGRAM_BOT_NAME
#         if TELEGRAM_BOT_NAME:
#             return f"https://t.me/{TELEGRAM_BOT_NAME}?start={self.invite_code}"
#         else:
#             return ValueError("TELEGRAM_BOT_NAME not set")


class Nudge(LifecycleModel):
    """
    A scheduled nudge or check-in with the user.

    Defines repeating rules. Uses a Step to script the interaction.
    StepJudgements will be run to provide context, and Transitions and
    conditions may be used to determine the next step (although if no
    Transitions are specified then the current step would be preserved).

    Scheduled nudges are actioned by calling respond(turn) on a leaf
    node in a conversation, at the appropriate time.
    """

    def __str__(self):
        return f"Nudge using {self.step_to_use}. {self.schedule}, {self.for_a_period_of}"

    intervention = models.ManyToManyField(
        "Intervention",
        related_name="nudges",
        blank=False,
    )
    nudge_during = models.ManyToManyField(
        "Step",
        blank=True,
        help_text="Which Steps should this Nudge be applied to. If blank, applies to all Steps",
        related_name="nudges",
    )

    step_to_use = models.ForeignKey(
        "Step",
        help_text="Which Step to use as a script for the Nudge",
        on_delete=models.CASCADE,
        related_name="used_by_nudges",
    )

    schedule = models.CharField(
        max_length=1024,
        null=False,
        blank=False,
        default="every week on Friday at 8pm",
        help_text="A natural language string (in English) defining the pattern of repeats, following the last client-initiated turn. E.g. 'every 30 minutes', 'every tue and thur at 1pm' or 'every weekday at 9am'.",
    )

    for_a_period_of = models.CharField(
        max_length=1024,
        null=False,
        blank=False,
        default="3 weeks",
        help_text="Natural language string defining how long the repeating rule should apply for. Based on the LAST client-initiated turn. E.g. '4 hours', '3 weeks' or '1 year'",
    )

    not_within_n_minutes = models.PositiveSmallIntegerField(
        default=60,
        help_text="If set, the nudge will not be scheduled within this many hours of the last client-initiated turn in the conversation.",
    )

    def end_date_(self, reference_datetime):
        parsed_duration = dateparser.parse(
            "after " + self.for_a_period_of, settings={"RELATIVE_BASE": reference_datetime}
        )

        if parsed_duration is None:
            raise ValueError(f"Invalid period: {self.for_a_period_of}")

        end_date = timezone.make_aware(parsed_duration)

        if end_date > reference_datetime:
            return end_date
        else:
            return reference_datetime

    def scheduled_datetimes(self, reference_datetime):
        earliest_allowed = reference_datetime + timedelta(minutes=self.not_within_n_minutes)
        end_date = self.end_date_(reference_datetime)
        r = RecurringEvent(now_date=reference_datetime)
        r.parse(self.schedule)
        if not r.get_RFC_rrule():
            raise Exception(f"Invalid schedule: {self.schedule}")

        rrl = iter(rrule.rrulestr(r.get_RFC_rrule()))
        while True:
            try:
                d = timezone.make_aware(rrl.__next__())
                if d < earliest_allowed:
                    continue
                if d < end_date:
                    yield d
                else:
                    break
            except StopIteration:
                break


class ScheduledNudgeManager(models.Manager):
    def due_now(self, reference_datetime=None):
        """
        Returns the latest ScheduledNudge per Turn that is due now and not completed.
        """
        if not reference_datetime:
            reference_datetime = timezone.now()

        subquery = (
            self.filter(
                turn=OuterRef("turn"),
                due__lte=reference_datetime,  # Ensure it's actually due
                completed=False,  # Ensure it's still pending
            )
            .order_by("-due")
            .values("id")[:1]
        )  # Select the latest due one

        return self.filter(id__in=Subquery(subquery))


class ScheduledNudge(LifecycleModel):

    objects = ScheduledNudgeManager()

    turn = models.ForeignKey("Turn", on_delete=models.CASCADE, related_name="nudges")
    nudge = models.ForeignKey("Nudge", on_delete=models.CASCADE, related_name="scheduled_nudges")

    due = models.DateTimeField(blank=True, null=True)
    completed = models.BooleanField(default=False)
    completed_turn = models.ForeignKey(
        "Turn", on_delete=models.CASCADE, related_name="completed_nudges", null=True, blank=True
    )

    class Meta:
        ordering = ["due"]


@receiver(post_save, sender=Turn)
def schedule_nudges_after_turn(sender, instance, created, **kwargs):
    """
    When a new Turn is created, check if any nudges should be scheduled
    and create the corresponding ScheduledNudge objects.
    """
    if not created:  # Only act on new Turns, not updates
        return

    conversation = instance.conversation
    conver_intervs = conversation.interventions()
    if not conver_intervs:
        return  # No interventions, so no nudges apply

    # Find last intervention step
    last_turn_with_step = conversation.turns.filter(step__isnull=False).last()
    last_interv_step = last_turn_with_step.step if last_turn_with_step else None

    # Find applicable nudges
    poss_nudges = Nudge.objects.filter(intervention__in=conver_intervs)
    if last_interv_step:
        poss_nudges = poss_nudges.filter(Q(nudge_during=last_interv_step) | Q(nudge_during=None))

    # Create ScheduledNudges for each applicable nudge
    snlist = []
    for i in poss_nudges:
        for j in i.scheduled_datetimes(instance.timestamp):
            snlist.append(ScheduledNudge(turn=instance, nudge=i, due=j))

    # Delete previous scheduled nudges and bulk insert all new objects
    ScheduledNudge.objects.filter(completed=False, turn__conversation=conversation).delete()
    if snlist:
        logger.info(f"Scheduling {len(snlist)} nudges for turn {instance.uuid}")
        ScheduledNudge.objects.bulk_create(snlist)
