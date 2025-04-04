# Generated by Django 5.1.5 on 2025-02-10 00:27

import autoslug.fields
import django.contrib.auth.models
import django.contrib.auth.validators
import django.db.models.deletion
import django.utils.timezone
import django_lifecycle.mixins
import pgvector.django.indexes
import pgvector.django.vector
import shortuuidfield.fields
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="Conversation",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=(django_lifecycle.mixins.LifecycleModelMixin, models.Model),
        ),
        migrations.CreateModel(
            name="Intervention",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("title", models.CharField(max_length=255)),
                ("short_title", models.CharField(max_length=20)),
                (
                    "slug",
                    autoslug.fields.AutoSlugField(
                        editable=False, populate_from="short_title", unique=True
                    ),
                ),
                ("version", models.CharField(editable=False, max_length=64, null=True)),
                ("sem_ver", models.CharField(max_length=64, null=True)),
            ],
            bases=(django_lifecycle.mixins.LifecycleModelMixin, models.Model),
        ),
        migrations.CreateModel(
            name="LLM",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "model_name",
                    models.CharField(
                        help_text="Litellm model name, e.g. llama3.2 or gpt-4o", max_length=255
                    ),
                ),
                (
                    "api_key",
                    models.CharField(
                        blank=True,
                        help_text="Litellm API key, defaults to LITELLM_API_KEY",
                        max_length=255,
                        null=True,
                    ),
                ),
                (
                    "base_url",
                    models.CharField(
                        blank=True,
                        help_text="Litellm base URL defaults to LITELLM_ENDPOINT",
                        max_length=1024,
                        null=True,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="CustomUser",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("password", models.CharField(max_length=128, verbose_name="password")),
                (
                    "last_login",
                    models.DateTimeField(blank=True, null=True, verbose_name="last login"),
                ),
                (
                    "is_superuser",
                    models.BooleanField(
                        default=False,
                        help_text="Designates that this user has all permissions without explicitly assigning them.",
                        verbose_name="superuser status",
                    ),
                ),
                (
                    "username",
                    models.CharField(
                        error_messages={"unique": "A user with that username already exists."},
                        help_text="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.",
                        max_length=150,
                        unique=True,
                        validators=[django.contrib.auth.validators.UnicodeUsernameValidator()],
                        verbose_name="username",
                    ),
                ),
                (
                    "first_name",
                    models.CharField(blank=True, max_length=150, verbose_name="first name"),
                ),
                (
                    "last_name",
                    models.CharField(blank=True, max_length=150, verbose_name="last name"),
                ),
                (
                    "email",
                    models.EmailField(blank=True, max_length=254, verbose_name="email address"),
                ),
                (
                    "is_staff",
                    models.BooleanField(
                        default=False,
                        help_text="Designates whether the user can log into this admin site.",
                        verbose_name="staff status",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Designates whether this user should be treated as active. Unselect this instead of deleting accounts.",
                        verbose_name="active",
                    ),
                ),
                (
                    "date_joined",
                    models.DateTimeField(
                        default=django.utils.timezone.now, verbose_name="date joined"
                    ),
                ),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("system_developer", "System Developer"),
                            ("intervention_developer", "Intervention Developer"),
                            ("client", "Client"),
                            ("supervisor", "Supervisor"),
                            ("therapist", "Therapist"),
                        ],
                        default="client",
                        max_length=30,
                    ),
                ),
                (
                    "groups",
                    models.ManyToManyField(
                        blank=True,
                        help_text="The groups this user belongs to. A user will get all permissions granted to each of their groups.",
                        related_name="user_set",
                        related_query_name="user",
                        to="auth.group",
                        verbose_name="groups",
                    ),
                ),
                (
                    "user_permissions",
                    models.ManyToManyField(
                        blank=True,
                        help_text="Specific permissions for this user.",
                        related_name="user_set",
                        related_query_name="user",
                        to="auth.permission",
                        verbose_name="user permissions",
                    ),
                ),
            ],
            options={
                "verbose_name": "user",
                "verbose_name_plural": "users",
                "abstract": False,
            },
            managers=[
                ("objects", django.contrib.auth.models.UserManager()),
            ],
        ),
        migrations.CreateModel(
            name="Judgement",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("prompt_template", models.TextField()),
                ("title", models.CharField(max_length=255)),
                (
                    "variable_name",
                    autoslug.fields.AutoSlugField(max_length=255, unique_with=("intervention",)),
                ),
                (
                    "intervention",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="mindframe.intervention"
                    ),
                ),
            ],
            options={
                "unique_together": {("intervention", "title")},
            },
        ),
        migrations.AddField(
            model_name="intervention",
            name="default_chunking_model",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="default_for_chunking",
                to="mindframe.llm",
            ),
        ),
        migrations.AddField(
            model_name="intervention",
            name="default_conversation_model",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="default_for_conversations",
                to="mindframe.llm",
            ),
        ),
        migrations.AddField(
            model_name="intervention",
            name="default_judgement_model",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="default_for_judgements",
                to="mindframe.llm",
            ),
        ),
        migrations.CreateModel(
            name="Step",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("title", models.CharField(max_length=255)),
                ("order", models.PositiveSmallIntegerField(default=1)),
                ("slug", autoslug.fields.AutoSlugField(editable=False, populate_from="title")),
                ("prompt_template", models.TextField()),
                (
                    "intervention",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="steps",
                        to="mindframe.intervention",
                    ),
                ),
            ],
            options={
                "ordering": ["intervention", "order", "title"],
            },
        ),
        migrations.CreateModel(
            name="StepJudgement",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "when",
                    models.CharField(
                        choices=[
                            ("turn", "Each turn"),
                            ("enter", "When entering the step"),
                            ("exit", "When exiting the step"),
                        ],
                        default="turn",
                        max_length=10,
                    ),
                ),
                (
                    "once",
                    models.BooleanField(
                        default=False,
                        help_text="Once we have a non-null value returned, don't repeat.",
                    ),
                ),
                (
                    "judgement",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="stepjudgements",
                        to="mindframe.judgement",
                    ),
                ),
                (
                    "step",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="stepjudgements",
                        to="mindframe.step",
                    ),
                ),
            ],
            options={
                "unique_together": {("judgement", "step", "when")},
            },
        ),
        migrations.AddField(
            model_name="step",
            name="judgements",
            field=models.ManyToManyField(
                through="mindframe.StepJudgement", to="mindframe.judgement"
            ),
        ),
        migrations.CreateModel(
            name="Turn",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("lft", models.PositiveIntegerField(db_index=True)),
                ("rgt", models.PositiveIntegerField(db_index=True)),
                ("tree_id", models.PositiveIntegerField(db_index=True)),
                ("depth", models.PositiveIntegerField(db_index=True)),
                (
                    "uuid",
                    shortuuidfield.fields.ShortUUIDField(
                        blank=True, editable=False, max_length=22, unique=True
                    ),
                ),
                ("timestamp", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "branch",
                    models.BooleanField(
                        default=False,
                        help_text="Is this a an alternative version of something that was said in the main conversation? I.e. was it used to create a branch in the conversation tree - perhaps to collate alternatives for a particular turn?",
                    ),
                ),
                (
                    "branch_reason",
                    models.CharField(
                        choices=[
                            ("main", "Not a branch - part of the main trunk of the conversation"),
                            ("expert", "Expert completion/imagined alternative"),
                            ("play", "Simulation/reset to create alternative line of conversation"),
                        ],
                        default="main",
                        max_length=25,
                    ),
                ),
                ("text", models.TextField(blank=True, null=True)),
                (
                    "text_source",
                    models.CharField(
                        choices=[("human", "Human"), ("AI", "AI")], default="human", max_length=25
                    ),
                ),
                ("embedding", pgvector.django.vector.VectorField(dimensions=1024, null=True)),
                (
                    "branch_author",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="counterfactual_turns",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "conversation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="turns",
                        to="mindframe.conversation",
                    ),
                ),
                (
                    "speaker",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="turns",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "step",
                    models.ForeignKey(
                        blank=True,
                        help_text="The Step used to generate this contribution to the conversation. If null, contributed by a human speaker.",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="generated_turns",
                        to="mindframe.step",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="Note",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "uuid",
                    shortuuidfield.fields.ShortUUIDField(
                        blank=True, editable=False, max_length=22, unique=True
                    ),
                ),
                ("timestamp", models.DateTimeField(default=django.utils.timezone.now)),
                ("inputs", models.JSONField(blank=True, default=dict, null=True)),
                ("data", models.JSONField(blank=True, default=dict, null=True)),
                (
                    "judgement",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notes",
                        to="mindframe.judgement",
                    ),
                ),
                (
                    "turn",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notes",
                        to="mindframe.turn",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Memory",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("text", models.TextField()),
                (
                    "intervention",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memories",
                        to="mindframe.intervention",
                    ),
                ),
                (
                    "turn",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="mindframe.turn",
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "Memories",
            },
            bases=(django_lifecycle.mixins.LifecycleModelMixin, models.Model),
        ),
        migrations.AlterUniqueTogether(
            name="intervention",
            unique_together={("title", "version", "sem_ver")},
        ),
        migrations.CreateModel(
            name="MemoryChunk",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "embedded_text",
                    models.TextField(
                        blank=True,
                        help_text="The actual text embedded (may include extra tokens to contextualise/summarise passage to aid matching)",
                        null=True,
                    ),
                ),
                (
                    "start",
                    models.IntegerField(
                        help_text="The start position of the chunk in the memory (chars)"
                    ),
                ),
                (
                    "end",
                    models.IntegerField(help_text="The end position of the chunk in the memory"),
                ),
                ("embedding", pgvector.django.vector.VectorField(dimensions=1024, null=True)),
                (
                    "memory",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chunks",
                        to="mindframe.memory",
                    ),
                ),
            ],
            options={
                "indexes": [
                    pgvector.django.indexes.HnswIndex(
                        ef_construction=64,
                        fields=["embedding"],
                        m=16,
                        name="embedding_index",
                        opclasses=["vector_cosine_ops"],
                    )
                ],
            },
        ),
        migrations.AlterUniqueTogether(
            name="step",
            unique_together={("intervention", "slug"), ("intervention", "title")},
        ),
        migrations.CreateModel(
            name="Transition",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "conditions",
                    models.TextField(
                        blank=True,
                        help_text="Python code to evaluate before the transition can be be made. Each line is evaluated indendently and all must be True for the transition to be made. Variables created by Judgements are passed in as a dictionary.",
                    ),
                ),
                (
                    "from_step",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="transitions_from",
                        to="mindframe.step",
                    ),
                ),
                (
                    "to_step",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="transitions_to",
                        to="mindframe.step",
                    ),
                ),
            ],
            options={
                "unique_together": {("from_step", "to_step", "conditions")},
            },
        ),
    ]
