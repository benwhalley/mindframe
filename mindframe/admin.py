import io
from django.db import transaction
import logging
import pprint
from django.forms.models import model_to_dict
from django.contrib import admin
from django.db import models
from django.shortcuts import redirect
from django.urls import path
from django.utils.html import format_html
from django.utils import timezone
from django.conf import settings
from django.forms import Textarea
from django.utils.html import format_html, format_html_join
from django.urls import reverse
from django.db.models import Q
from django.contrib import admin, messages
from django.utils import timezone
from django.http import HttpResponse
import json
from django import forms
from django.shortcuts import render, redirect
from django.contrib import messages

import shortuuid
from django.contrib import admin
from .models import (
    CustomUser,
    Intervention,
    Cycle,
    TreatmentSession,
    Step,
    Transition,
    Turn,
    Note,
    Example,
    TreatmentSessionState,
    Judgement,
    StepJudgement,
    LLM,
    SyntheticConversation,
    LLMLog,
)


from mindframe.settings import MINDFRAME_SHORTUUID_ALPHABET
from mindframe.graphing import mermaid_diagram

from ruamel.yaml import YAML

yaml = YAML()
yaml.default_flow_style = False  # Use block style
yaml.width = 4096  # Avoid wrapping long lines into multiple lines
yaml.representer.add_representer(
    str, lambda dumper, data: dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
)

shortuuid.set_alphabet(MINDFRAME_SHORTUUID_ALPHABET)

logger = logging.getLogger(__name__)


class InterventionImportForm(forms.Form):
    file = forms.FileField(label="Select JSON file to import")


@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "role", "is_staff", "is_active")
    list_filter = ("role", "is_staff", "is_active")
    search_fields = ("username", "email")


class ExampleInline(admin.TabularInline):
    model = Example
    extra = 1


@admin.register(SyntheticConversation)
class SyntheticConversationAdmin(admin.ModelAdmin):
    pass


@admin.register(LLM)
class LLMAdmin(admin.ModelAdmin):
    search_fields = ["model_name"]
    list_display = ["model_name", "provider_name", "nickname"]


@admin.register(LLMLog)
class LLMLogAdmin(admin.ModelAdmin):
    list_display = [
        "timestamp",
        "log_type",
        "turn_id",
        "inference_for",
        "message",
    ]
    readonly_fields = [
        "prompt_text",
        "log_type",
        "session",
        "step",
        "model",
        "turn",
        "judgement",
        "timestamp",
        "message",
        "metadata",
        "metadata_neat",
    ]

    def turn_id(self, obj):
        return obj.turn and obj.turn.uuid[:5] + "…"

    def inference_for(self, obj):
        return obj.step and "Step" or obj.judgement and "Judgement" or "Unknown"

    exclude = [
        "metadata",
    ]
    search_fields = ["model__model_name", "step__title", "judgement__title", "session__uuid"]
    list_filter = ["log_type", "model", "judgement", "step"]
    date_hierarchy = "timestamp"

    def metadata_neat(self, obj):
        import pprint

        return format_html("<pre>{}</pre>", pprint.pformat(obj.metadata))


@admin.register(Cycle)
class CycleAdmin(admin.ModelAdmin):
    autocomplete_fields = ["intervention", "client"]
    list_display = ("start_date", "client", "intervention", "end_date")
    list_filter = ("start_date", "end_date")
    search_fields = ("client__username", "intervention__name")


class TreatmentSessionStateInline(admin.TabularInline):
    model = TreatmentSessionState
    extra = 0
    max_num = 0
    readonly_fields = [
        "timestamp",
        "previous_step",
        "step",
    ]


class TransitionInline(admin.TabularInline):
    model = Transition
    fk_name = "from_step"
    extra = 1
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
    extra = 1
    autocomplete_fields = ("judgement",)


@admin.register(Step)
class StepAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "intervention")
    autocomplete_fields = ("intervention",)
    search_fields = ("title", "intervention__title")
    list_filter = ("intervention",)
    inlines = [
        StepJudgementInline,
        TransitionInline,
    ]
    formfield_overrides = {
        models.TextField: {
            "widget": Textarea(
                attrs={
                    "rows": 20,
                    "cols": 100,
                    "style": "resize: vertical; font-size: 10px; font-family:monospace;",
                }
            )
        },
    }


@admin.register(Transition)
class TransitionAdmin(admin.ModelAdmin):
    list_display = ("from_step", "to_step")
    list_filter = ("to_step__intervention",)
    search_fields = ("from_step__name", "to_step__name")


@admin.register(Turn)
class TurnAdmin(admin.ModelAdmin):
    list_display = (
        "speaker",
        "session_state__session__uuid",
        "text",
        "timestamp",
    )
    list_filter = ("speaker", "timestamp")
    search_fields = (
        "session_state__session__cycle__client__username",
        "session_state__session__uuid",
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "start_again/<int:turn_id>/",
                self.admin_site.admin_view(self.start_again_from_turn),
                name="start_again_from_turn",
            ),
        ]
        return custom_urls + urls

    def start_again_from_turn(self, request, turn_id):
        try:
            # Get the specified turn
            original_turn = Turn.objects.get(id=turn_id)
            original_session = original_turn.session_state.session
            turn_timestamp = original_turn.timestamp

            # 1. Duplicate the Cycle
            original_cycle = original_session.cycle
            new_cycle = Cycle.objects.create(
                client=original_cycle.client,
                intervention=original_cycle.intervention,
                start_date=timezone.now(),
            )

            # 2. Duplicate the TreatmentSession
            new_session = TreatmentSession.objects.create(cycle=new_cycle, started=timezone.now())

            # 3. Duplicate relevant TreatmentSessionStates
            tss_to_dupe = TreatmentSessionState.objects.filter(
                session=original_session, timestamp__lte=turn_timestamp
            ).order_by("timestamp")
            for state in tss_to_dupe:
                state.pk = None
                state.session = new_session
                state.save()

            # 4. Duplicate Turns and Notes before the turn timestamp
            turns_to_duplicate = Turn.objects.filter(
                session_state__session=original_session,
                timestamp__lte=turn_timestamp,
            )
            for turn in turns_to_duplicate:
                logs_ids = turn.llm_calls.all().values("id")  # get the ids of the LLM logs
                turn.pk = None  # reset primary key to create new object
                turn.uuid = shortuuid.uuid()
                turn.session_state = new_session.state  # Attach to new session
                turn.save()
                # we don't duplicate LLM Log objects, but do reference them in the new turn
                turn.llm_calls.add(*LLMLog.objects.filter(id__in=logs_ids))

            notes_to_duplicate = Note.objects.filter(
                turn__session_state__session=original_session,
                timestamp__lte=turn_timestamp,
            )
            for note in notes_to_duplicate:
                note.pk = None
                note.uuid = shortuuid.uuid()
                note.turn = turn
                note.save()

            # Redirect to chatbot interface for the new session
            return redirect(f"{settings.CHAT_URL}/?session_id={new_session.uuid}")

        except Exception as e:
            logger.error(f"An error occurred while starting again: {e}")
            self.message_user(
                request, f"An error occurred while starting again: {e}", level=messages.ERROR
            )
            return redirect("admin:mindframe_turn_change", turn_id)


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("turn__id", "judgement", "val", "timestamp")
    list_filter = ("timestamp", "judgement")
    readonly_fields = ["turn", "judgement", "timestamp", "pprint_inputs", "pprint_data"]
    search_fields = ("turn__session_state__session__cycle__client__username",)
    autocomplete_fields = [
        "turn",
    ]

    def pprint_inputs(self, obj):
        return format_html("<pre>{}</pre>", pprint.pformat(obj.inputs, compact=True))

    def pprint_data(self, obj):
        return format_html("<pre>{}</pre>", pprint.pformat(obj.data, compact=True))

    pprint_inputs.short_description = "Inputs"
    pprint_data.short_description = "Data"


@admin.register(Judgement)
class JudgementAdmin(admin.ModelAdmin):
    list_display = ("variable_name", "title", "task_summary", "slug", "intervention")
    autocomplete_fields = [
        "intervention",
    ]
    search_fields = ["title", "variable_name", "intervention__title"]
    list_editable = [
        "title",
        "task_summary",
    ]


@admin.register(Example)
class ExampleAdmin(admin.ModelAdmin):
    list_display = ("intervention", "title")
    list_filter = ("intervention",)
    autocomplete_fields = ["intervention"]
    search_fields = (
        "title",
        "intervention__title",
        "text",
    )


@admin.register(TreatmentSessionState)
class TreatmentSessionStateAdmin(admin.ModelAdmin):
    list_display = ("session", "step", "timestamp")
    search_fields = ("session__cycle__client__username", "step__title")


@admin.register(Intervention)
class InterventionAdmin(admin.ModelAdmin):
    list_display = ("title_version", "ver", "slug", "short_title", "start_session_button")
    search_fields = ("title",)
    inlines = [ExampleInline]
    readonly_fields = ["slug", "version"]
    autocomplete_fields = ["default_conversation_model", "default_judgement_model"]

    def title_version(self, obj):
        return f"{obj.title} ({obj.sem_ver})"

    def ver(self, obj):
        return obj.ver()

    def start_session_button(self, obj):
        url = reverse("admin:start_session", args=[obj.id])
        return format_html(f'<a class="button" href="{url}">New Session</a>')

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
            {"intervention": intervention, "mermaid_code": self.mermaid_diagram(intervention)},
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
                "<int:object_id>/mermaid/",
                self.admin_site.admin_view(self.render_mermaid_view),
                name="mermaid_diagram",
            ),
        ]
        return custom_urls + urls

    def export_intervention(self, request, object_id):
        intervention = Intervention.objects.filter(pk=object_id).first()

        # all fields except id
        step_fields = [f.name for f in Step._meta.get_fields() if f.name != "id"]
        judgement_fields = [f.name for f in Judgement._meta.get_fields() if f.name != "id"]
        example_fields = [f.name for f in Example._meta.get_fields() if f.name != "id"]

        related_objects = {
            "intervention": model_to_dict(intervention, fields=Intervention.exported_fields),
            "steps": list(intervention.steps.values(*Step.exported_fields)),
            "judgements": list(
                Judgement.objects.filter(intervention=intervention).values(
                    *Judgement.exported_fields
                )
            ),
            "examples": list(intervention.examples.values(*Example.exported_fields)),
            # note we need to handle these differently on import
            "transitions": list(
                Transition.objects.filter(to_step__intervention=intervention).values(
                    *Transition.exported_fields
                )
            ),
        }

        # Serialize
        stream = io.StringIO()
        yaml.dump(related_objects, stream)
        stream.seek(0)

        response = HttpResponse(
            stream.read(),
            content_type="application/yaml",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="intervention_{intervention.slug}.yaml"'
        )
        return response

    def import_intervention(self, request):
        if request.method == "POST":
            form = InterventionImportForm(request.POST, request.FILES)
            if form.is_valid():
                with transaction.atomic():
                    file = form.cleaned_data["file"]
                    try:
                        data = yaml.load(file)
                        intervention_data = data.pop("intervention")

                        # Generate a new semantic version (you can customize this logic)
                        new_sem_ver = f"{intervention_data.get('sem_ver', '1.0.1')}-imported"

                        # Create a new intervention with a different version
                        intervention = Intervention.objects.create(
                            title=f"{intervention_data['title']} (Imported)",
                            short_title=intervention_data["short_title"],
                            slug=None,  # Let AutoSlugField generate a new slug
                            sem_ver=new_sem_ver,
                        )

                        # Keep a mapping of old IDs to new instances for steps and judgements
                        step_mapping = {}
                        judgement_mapping = {}

                        # Create the mapping during step import
                        step_mapping = {}
                        for step_data in data["steps"]:
                            step_data.pop("id", None)  # Remove the original ID
                            step_data["intervention_id"] = intervention.id
                            new_step = Step.objects.create(**step_data)
                            step_mapping[new_step.slug] = new_step

                        # Import Judgements
                        for judgement_data in data["judgements"]:
                            judgement_data.pop("id", None)  # Remove the original ID
                            judgement_data["intervention_id"] = intervention.id
                            new_judgement = Judgement.objects.create(**judgement_data)
                            judgement_mapping[judgement_data["variable_name"]] = new_judgement

                        # Import Examples
                        for example_data in data["examples"]:
                            example_data.pop("id", None)  # Remove the original ID
                            example_data["intervention_id"] = intervention.id
                            Example.objects.create(**example_data)

                        # Import Transitions
                        # note we lookup by slug among the NEWLY CREATED ste[]
                        for transition_data in data["transitions"]:

                            transition_data["from_step"] = step_mapping[
                                transition_data.pop("from_step__slug")
                            ]
                            transition_data["to_step"] = step_mapping[
                                transition_data.pop("to_step__slug")
                            ]
                            # Create the new Transition object
                            Transition.objects.create(**transition_data)

                        messages.success(
                            request,
                            f"Imported Intervention '{intervention.title}' with version '{new_sem_ver} ({intervention.ver()})'.",
                        )
                        return redirect("admin:mindframe_intervention_changelist")
                    except Exception as e:
                        messages.error(request, f"Error importing intervention: {e}")
        else:
            form = InterventionImportForm()

        context = {
            "form": form,
            "title": "Import Intervention",
        }
        return render(request, "admin/intervention_import.html", context)

    def start_session(self, request, intervention_id):
        intervention = Intervention.objects.get(pk=intervention_id)
        client = request.user
        cycle = Cycle.objects.create(intervention=intervention, client=client)
        session = TreatmentSession.objects.create(
            cycle=cycle,
            started=timezone.now(),
        )
        return redirect(f"{settings.CHAT_URL}/?session_id={session.uuid}")

    def change_view(self, request, object_id, form_url="", extra_context=None):

        extra_context = extra_context or {}
        extra_context.update(
            {
                "new_session": reverse(
                    "admin:start_session",
                    args=[
                        object_id,
                    ],
                ),
                "diagram": reverse(
                    "admin:mermaid_diagram",
                    args=[
                        object_id,
                    ],
                ),
                "mermaid": self.mermaid_diagram(self.get_object(request, object_id)),
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


@admin.register(TreatmentSession)
class TreatmentSessionAdmin(admin.ModelAdmin):
    save_on_top = True
    autocomplete_fields = ["cycle"]
    list_display = (
        "id",
        "n_turns",
        "chatbot_link",
        "view_link",
        "uuid",
        "cycle__id",
        "state",
        "started",
        "last_updated",
        "uuid",
        # "clinical_notes",  # Add this to display related notes in the list view
    )
    list_filter = ("cycle__intervention__short_title", "started", "last_updated")
    search_fields = (
        "uuid",
        "cycle__client__username",
    )
    inlines = [TreatmentSessionStateInline]
    readonly_fields = ["cycle", "uuid", "started", "last_updated", "clinical_notes"]

    # Override to add `clinical_notes` in the change view
    fieldsets = (
        (
            None,
            {
                "fields": ["cycle", "uuid", "started", "last_updated", "clinical_notes"],
            },
        ),
    )

    def n_turns(self, obj):
        return obj.turns.count()

    def clinical_notes(self, obj):
        notes = Note.objects.filter(turn__session_state__session=obj)
        if not notes.exists():
            return "No notes available"
        return format_html_join(
            "\n",
            "<p><strong>{}</strong>: {} ({})</p>",
            ((note.judgement.variable_name, note.val(), note.timestamp) for note in notes),
        )

    clinical_notes.short_description = "Clinical Notes/Judgements"

    def chatbot_link(self, obj):
        return format_html('<a href="{}" target="_blank">Continue</a>', obj.chatbot_link())

    chatbot_link.short_description = "Chat"

    def view_link(self, obj):
        return format_html('<a href="{}" target="_blank">View</a>', obj.get_absolute_url())

    view_link.short_description = "View"
