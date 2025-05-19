import logging
import pprint

import shortuuid
from django.conf import settings
from django.contrib import admin
from django.db import models
from django.forms import Textarea
from django.forms.models import model_to_dict
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from ruamel.yaml import YAML

from mindframe.graphing import mermaid_diagram
from mindframe.settings import MINDFRAME_SHORTUUID_ALPHABET, BranchReasons, TurnTypes
from mindframe.tree import create_branch

from .models import (
    LLM,
    Conversation,
    CustomUser,
    Interruption,
    Intervention,
    Judgement,
    Memory,
    MemoryChunk,
    Note,
    Nudge,
    ScheduledNudge,
    Step,
    StepJudgement,
    Transition,
    Turn,
)

yaml = YAML()
yaml.default_flow_style = False  # Use block style
yaml.width = 4096  # Avoid wrapping long lines into multiple lines
yaml.representer.add_representer(
    str,
    lambda dumper, data: dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|"),
)

shortuuid.set_alphabet(MINDFRAME_SHORTUUID_ALPHABET)

logger = logging.getLogger(__name__)


@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "role", "is_staff", "is_active")
    list_filter = ("role", "is_staff", "is_active")
    search_fields = ("username", "email")
    filter_horizontal = ("user_permissions",)


class MemoryChunkInline(admin.TabularInline):
    model = MemoryChunk
    extra = 0
    max_num = 0
    readonly_fields = [
        "memory",
    ]


@admin.register(Memory)
class MemoryAdmin(admin.ModelAdmin):
    inlines = [MemoryChunkInline]
    autocomplete_fields = ["intervention", "turn"]


@admin.register(MemoryChunk)
class MemoryChunkAdmin(admin.ModelAdmin):
    pass


class IsSyntheticFilter(admin.SimpleListFilter):
    title = "is synthetic"
    parameter_name = "is_synthetic"

    def lookups(self, request, model_admin):
        return (
            ("True", "Yes"),
            ("False", "No"),
        )

    def queryset(self, request, queryset):
        if self.value() == "True":
            return queryset.filter(is_synthetic=True)
        if self.value() == "False":
            return queryset.filter(is_synthetic=False)
        return queryset


class TurnInline(admin.TabularInline):
    model = Turn
    fields = [
        "timestamp",
        "depth",
        "branch",
        "step",
        "speaker",
        "text",
        "metadata",
        "notes_data",
        "branch_button",
    ]

    readonly_fields = [
        "timestamp",
        "depth",
        "branch",
        "step",
        "speaker",
        "text",
        "metadata",
        "notes_data",
        "branch_button",
    ]
    extra = 0
    ordering = ["depth", "timestamp"]

    def branch_button(self, obj):
        if not obj.pk:
            # Inline is in "add" mode and hasn't been saved yet
            return ""
        url = reverse("admin:conversation_branch_turn", args=[obj.pk])
        return format_html('<a class="button" href="{}">Branch here</a>', url)

    branch_button.short_description = "Branch"


class NoteInline(admin.TabularInline):
    model = Note
    fields = [
        "timestamp",
        "judgement",
        "data",
    ]
    readonly_fields = [
        "timestamp",
        "judgement",
        "data",
    ]
    extra = 0
    ordering = ["timestamp"]


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    save_on_top = True
    list_filter = (IsSyntheticFilter, "archived", "turns__step__intervention")
    inlines = [TurnInline]
    readonly_fields = ["uuid"]
    list_display = [
        "__str__",
        "last_turn_timestamp",
        "summary",
        "speakers",
        "active",
        "n_turns",
        "intervention",
        "uuid",
    ]
    list_prefetch_related = ["intervention", "speakers", "turns"]
    search_fields = ["uuid", "turns__speaker__username", "turns__speaker__last_name"]

    def last_turn_timestamp(self, obj):
        last_turn = obj.turns.last()
        return last_turn.timestamp if last_turn else None

    def n_turns(self, obj):
        return obj.turns.count()

    def speakers(self, obj):
        return ",".join(
            set(
                filter(
                    bool,
                    obj.turns.all().values_list("speaker__username", flat=True).distinct(),
                )
            )
        )

    def intervention(self, obj):
        return ",".join(
            set(
                filter(
                    bool,
                    obj.turns.all().values_list("step__intervention__title", flat=True).distinct(),
                )
            )
        )

    def active(self, obj):
        return not obj.archived

    active.boolean = True

    def summary(self, obj):
        fn = (
            Note.objects.filter(turn__conversation=obj)
            .filter(judgement__variable_name__istartswith="summary")
            .last()
        )
        return fn and fn.val().RESPONSE_ or ""

    def branch_turn(self, request, turn_id, *args, **kwargs):
        """
        Admin view to handle 'Branch here' clicks from the TurnInline or anywhere.
        Supports an optional 'next' GET param for custom redirection.
        """
        turn = get_object_or_404(Turn, pk=turn_id)
        new_turn = create_branch(turn, reason=BranchReasons.PLAY)

        # If the user included ?next=some_url, redirect there; otherwise, go to conversation admin.
        next_loc = request.GET.get("next")
        if next_loc == "gradio":
            chaturl = new_turn.gradio_url(request)
            return redirect(chaturl)
        if next_loc == "branch":
            return redirect(reverse("conversation_detail", args=[new_turn.uuid]))
        else:
            return redirect(
                reverse("admin:mindframe_conversation_change", args=[turn.conversation.pk])
            )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "branch-turn/<int:turn_id>/",
                self.admin_site.admin_view(self.branch_turn),
                name="conversation_branch_turn",
            ),
        ]
        return custom_urls + urls


@admin.register(LLM)
class LLMAdmin(admin.ModelAdmin):
    search_fields = ["model_name"]
    list_display = [
        "model_name",
    ]


class TransitionInline(admin.TabularInline):
    model = Transition
    fk_name = "from_step"
    extra = 0
    autocomplete_fields = ("to_step",)

    formfield_overrides = {
        models.TextField: {
            "widget": admin.widgets.AdminTextareaWidget(attrs={"class": "transition-conditions"})
        }
    }

    class Media:
        css = {
            "all": ("mindframe/css/admin-extra.css",),
        }


class StepJudgementInline(admin.TabularInline):
    model = StepJudgement
    extra = 0
    autocomplete_fields = ("judgement",)


@admin.register(Step)
class StepAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "intervention",
        "order",
        "slug",
    )
    autocomplete_fields = ("intervention",)
    search_fields = ("title", "intervention__title")
    list_editable = ["order"]
    list_filter = ("intervention",)
    inlines = [
        StepJudgementInline,
        TransitionInline,
    ]

    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name == "prompt_template":
            kwargs["widget"] = Textarea(
                attrs={
                    "rows": 20,
                    "style": "width:100%; resize: vertical; font-size: 10px; font-family: monospace;",
                }
            )
        elif db_field.name == "opening_line":
            kwargs["widget"] = Textarea(
                attrs={
                    "rows": 3,
                    "style": "width 100%; resize: vertical;",
                }
            )
        return super().formfield_for_dbfield(db_field, **kwargs)


@admin.register(Transition)
class TransitionAdmin(admin.ModelAdmin):
    list_display = ("from_step", "to_step")
    list_filter = ("to_step__intervention",)
    search_fields = ("from_step__name", "to_step__name")


@admin.register(Turn)
class TurnAdmin(admin.ModelAdmin):
    list_display = (
        "text",
        "speaker",
        "timestamp",
        "uuid",
        "branch",
        "depth",
        "conversation__uuid",
    )
    list_filter = ("branch", "branch_reason")
    date_hierarchy = "timestamp"
    inlines = [NoteInline]
    list_select_related = ["conversation"]
    search_fields = (
        "uuid",
        "text",
        "speaker__username",
        "speaker__last_name",
        "conversation__uuid",
        "conversation__chat_room_id",
    )
    autocomplete_fields = [
        "resuming_from",
        "interruption",
        "speaker",
        "conversation",
        "step",
        "branch_author",
    ]


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("turn__uuid", "judgement", "val", "timestamp")

    list_filter = ("timestamp", "judgement")

    list_select_related = ["turn", "judgement", "judgement__intervention"]

    exclude = ["data"]
    readonly_fields = ["turn", "judgement", "timestamp", "pprint_data"]
    search_fields = ("turn__speaker__username",)
    autocomplete_fields = [
        "turn",
    ]

    def pprint_data(self, obj):
        return format_html("<pre>{}</pre>", pprint.pformat(obj.data, compact=True))

    pprint_data.short_description = "Data"


@admin.register(Judgement)
class JudgementAdmin(admin.ModelAdmin):
    list_display = (
        "variable_name",
        "prompt_template",
        "intervention",
    )
    autocomplete_fields = ["intervention", "model"]
    search_fields = ["variable_name", "intervention__title"]
    list_editable = [
        "prompt_template",
    ]


@admin.register(Intervention)
class InterventionAdmin(admin.ModelAdmin):
    list_display = (
        "title_version",
        "ver",
        "is_default_intervention",
        "intervention_type",
        "slug",
        "title",
        "start_session_button",
    )
    search_fields = ("title",)
    list_editable = ["is_default_intervention"]
    readonly_fields = ["version"]
    autocomplete_fields = [
        "default_conversation_model",
        "default_judgement_model",
        "default_chunking_model",
    ]

    def title_version(self, obj):
        return f"{obj.title} ({obj.sem_ver})"

    def ver(self, obj):
        return obj.ver()

    def start_session_button(self, obj):
        anon_url = reverse("start_gradio_chat", kwargs={"intervention_slug": obj.slug})
        return format_html(f'<a class="button" href="{anon_url}">New Anonymous Session</a> ')

    start_session_button.short_description = "Start Session"
    start_session_button.allow_tags = True

    def mermaid_diagram(self, obj):

        return mermaid_diagram(obj)

    mermaid_diagram.short_description = "Intervention Flowchart"

    def render_mermaid_view(self, request, object_id):
        """
        Displays the Mermaid diagram on a separate page.
        """
        intervention = self.get_object(request, object_id)
        return render(
            request,
            "admin/intervention_mermaid.html",
            {
                "intervention": intervention,
                "mermaid_code": self.mermaid_diagram(intervention),
            },
        )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:intervention_id>/new-session/",
                self.admin_site.admin_view(self.start_session),
                name="start_session",
            ),
            path(
                "<int:object_id>/export/",
                self.admin_site.admin_view(self.export_intervention),
                name="mindframe_export",
            ),
            path(
                "import/",
                self.admin_site.admin_view(self.import_intervention),
                name="import_intervention",
            ),
            path(
                "export/",
                self.admin_site.admin_view(self.export_intervention),
                name="export_intervention",
            ),
            path(
                "<int:object_id>/mermaid/",
                self.admin_site.admin_view(self.render_mermaid_view),
                name="mermaid_diagram",
            ),
        ]
        return custom_urls + urls

    def export_intervention(self, request, object_id):
        raise NotImplementedError("Exporting interventions is not yet implemented.")

    #         intervention = Intervention.objects.filter(pk=object_id).first()

    #         # all fields except id
    #         step_fields = [f.name for f in Step._meta.get_fields() if f.name != "id"]
    #         judgement_fields = [f.name for f in Judgement._meta.get_fields() if f.name != "id"]
    #         memory_fields = [f.name for f in Memory._meta.get_fields() if f.name != "id"]

    #         related_objects = {
    #             "intervention": model_to_dict(intervention, fields=Intervention.exported_fields),
    #             "steps": list(intervention.steps.values(*Step.exported_fields)),
    #             "judgements": list(
    #                 Judgement.objects.filter(intervention=intervention).values(
    #                     *Judgement.exported_fields
    #                 )
    #             ),
    #             "memories": list(intervention.memories.values(*Memory.exported_fields)),
    #             # note we need to handle these differently on import
    #             "transitions": list(
    #                 Transition.objects.filter(to_step__intervention=intervention).values(
    #                     *Transition.exported_fields
    #                 )
    #             ),
    #         }

    #         # Serialize
    #         stream = io.StringIO()
    #         yaml.dump(related_objects, stream)
    #         stream.seek(0)

    #         response = HttpResponse(
    #             stream.read(),
    #             content_type="application/yaml",
    #         )
    #         response["Content-Disposition"] = (
    #             f'attachment; filename="intervention_{intervention.slug}.yaml"'
    #         )
    #         return response

    def import_intervention(self, request):
        raise NotImplementedError("Importing interventions is not yet implemented.")

    #         if request.method == "POST":
    #             form = InterventionImportForm(request.POST, request.FILES)
    #             if form.is_valid():
    #                 with transaction.atomic():
    #                     file = form.cleaned_data["file"]
    #                     try:
    #                         data = yaml.load(file)
    #                         intervention_data = data.pop("intervention")

    #                         # Generate a new semantic version (you can customize this logic)
    #                         new_sem_ver = f"{intervention_data.get('sem_ver', '1.0.1')}-imported"

    #                         # Create a new intervention with a different version
    #                         intervention = Intervention.objects.create(
    #                             title=f"{intervention_data['title']} (Imported)",
    #                             short_title=intervention_data["short_title"],
    #                             slug=None,  # Let AutoSlugField generate a new slug
    #                             sem_ver=new_sem_ver,
    #                         )

    #                         # Keep a mapping of old IDs to new instances for steps and judgements
    #                         step_mapping = {}
    #                         judgement_mapping = {}

    #                         # Create the mapping during step import
    #                         step_mapping = {}
    #                         for step_data in data["steps"]:
    #                             step_data.pop("id", None)  # Remove the original ID
    #                             step_data["intervention_id"] = intervention.id
    #                             new_step = Step.objects.create(**step_data)
    #                             step_mapping[new_step.slug] = new_step

    #                         # Import Judgements
    #                         for judgement_data in data["judgements"]:
    #                             judgement_data.pop("id", None)  # Remove the original ID
    #                             judgement_data["intervention_id"] = intervention.id
    #                             new_judgement = Judgement.objects.create(**judgement_data)
    #                             judgement_mapping[judgement_data["variable_name"]] = new_judgement

    #                         # Import Examples
    #                         for example_data in data["examples"]:
    #                             example_data.pop("id", None)  # Remove the original ID
    #                             example_data["intervention_id"] = intervention.id
    #                             Example.objects.create(**example_data)

    #                         # Import Transitions
    #                         # note we lookup by slug among the NEWLY CREATED ste[]
    #                         for transition_data in data["transitions"]:

    #                             transition_data["from_step"] = step_mapping[
    #                                 transition_data.pop("from_step__slug")
    #                             ]
    #                             transition_data["to_step"] = step_mapping[
    #                                 transition_data.pop("to_step__slug")
    #                             ]
    #                             # Create the new Transition object
    #                             Transition.objects.create(**transition_data)

    #                         messages.success(
    #                             request,
    #                             f"Imported Intervention '{intervention.title}' with version '{new_sem_ver} ({intervention.ver()})'.",
    #                         )
    #                         return redirect("admin:mindframe_intervention_changelist")
    #                     except Exception as e:
    #                         messages.error(request, f"Error importing intervention: {e}")
    #         else:
    #             form = InterventionImportForm()

    #         context = {
    #             "form": form,
    #             "title": "Import Intervention",
    #         }
    #         return render(request, "admin/intervention_import.html", context)

    def start_session(self, request, intervention_id):
        intervention = Intervention.objects.get(pk=intervention_id)
        step = intervention.steps.all().first()
        therapist, _ = CustomUser.objects.get_or_create(
            username="therapist",
            defaults={"role": "therapist", "email": "linda@example.com"},
        )
        conversation = Conversation.objects.create()
        human_starter = Turn.add_root(
            conversation=conversation,
            speaker=request.user,
            text="",
            turn_type=TurnTypes.OPENING,
        )

        bot_turn = human_starter.add_child(
            conversation=conversation,
            speaker=therapist,
            text=step.opening_line,
            turn_type=TurnTypes.OPENING,
            step=step,
        )

        return redirect(f"{settings.CHAT_URL}/?turn_id={bot_turn.uuid}")

    def change_view(self, request, object_id, form_url="", extra_context=None):

        extra_context = extra_context or {}
        obj = self.get_object(request, object_id)
        extra_context.update(
            {
                "diagram": reverse(
                    "admin:mermaid_diagram",
                    args=[
                        object_id,
                    ],
                ),
                "mermaid": self.mermaid_diagram(obj),
                "start_new_chat_link": settings.WEB_URL
                + reverse("start_gradio_chat", kwargs={"intervention_slug": obj.slug}),
            }
        )

        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    class Media:
        js = [
            "https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js",  # Include Mermaid.js
        ]
        css = {
            "all": ("mindframe/css/admin-extra.css",),  # Optional custom admin styles
        }


@admin.register(Nudge)
class NudgeAdmin(admin.ModelAdmin):
    autocomplete_fields = ["intervention", "nudge_during", "step_to_use"]
    search_fields = ["intervention__title", "step_to_use__title"]
    readonly_fields = ["example_dates"]

    def example_dates(self, obj):
        try:
            scheduled_datetimes = list(obj.scheduled_datetimes(timezone.now()))
            if not len(scheduled_datetimes):
                return format_html("No times scheduled, check the syntax")
            # todo check length of scheduled_datetimes first and limit display
            return format_html_join(
                "\n",
                "<li>{}</li>",
                ((dt.strftime("%Y-%m-%d %H:%M"),) for dt in scheduled_datetimes),
            )
        except Exception as e:
            return str(e)

    example_dates.short_description = "Example dates the nudge would be made"
    example_dates.help_text = (
        "This shows a preview of the next scheduled nudges assuming the last turn was now."
    )


class DueNowFilter(admin.SimpleListFilter):
    title = "Due Now"
    parameter_name = "due_now"

    def lookups(self, request, model_admin):
        return [
            ("yes", "Due Now"),
            ("no", "Not Due Yet"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return ScheduledNudge.objects.due_now()
        elif self.value() == "no":
            return ScheduledNudge.objects.filter(due__gt=timezone.now())
        return queryset


class DueSoonFilter(admin.SimpleListFilter):
    title = "Due Soon"
    parameter_name = "due_soon"

    def lookups(self, request, model_admin):
        return [
            ("1", "Due next 1 min"),
            ("5", "Due next 5 mins"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "1":
            return ScheduledNudge.objects.due_now(timezone.now() + timezone.timedelta(minutes=1))
        elif self.value() == "5":
            return ScheduledNudge.objects.due_now(timezone.now() + timezone.timedelta(minutes=5))
        return queryset


@admin.register(ScheduledNudge)
class ScheduledNudgeAdmin(admin.ModelAdmin):
    autocomplete_fields = [
        "turn",
        "completed_turn",
        "nudge",
    ]
    list_display = [
        # "turn",
        "due",
        "completed",
        "nudge__step_to_use",
        "nudge__schedule",
        "nudge__for_a_period_of",
    ]
    list_filter = ["completed", DueNowFilter, DueSoonFilter]
    date_hierarchy = "due"
    # readonly_fields = [
    #     # "completed_turn",
    #     "completed",
    #     "nudge",
    #     # "turn",
    # ]


@admin.register(Interruption)
class InterruptionAdmin(admin.ModelAdmin):
    autocomplete_fields = [
        "intervention",
        "trigger_judgement",
        "resolution_judgement",
        "target_step",
    ]
    search_fields = ["intervention__title", "target_step__title"]
    list_display = [
        "intervention",
        "target_step",
        "trigger",
        "resolution",
    ]
