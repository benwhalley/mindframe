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
    SyntheticConversation,
)


from mindframe.settings import MINDFRAME_SHORTUUID_ALPHABET
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
    readonly_fields = ["timestamp", "previous_step", "step", "start_again_button"]

    def start_again_button(self, obj):
        """Button to duplicate the session and start again from this state."""
        url = reverse("admin:start_again", args=[obj.session.pk, obj.pk])
        return format_html('<a class="button" href="{}">Restart Chat from here</a>', url)

    start_again_button.short_description = "Actions"


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
        "session_state__id",
        "session_state",
        "text",
        "timestamp",
    )
    list_filter = ("speaker", "timestamp")
    search_fields = ("session__cycle__client__username",)


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("session_state", "judgement", "val", "timestamp")
    list_filter = ("timestamp", "judgement")
    readonly_fields = ["session_state", "judgement", "timestamp", "pprint_inputs", "pprint_data"]
    search_fields = ("session_state__session__cycle__client__username",)
    autocomplete_fields = [
        "session_state",
    ]

    def pprint_inputs(self, obj):
        return format_html("<pre>{}</pre>", pprint.pformat(obj.inputs, compact=True))

    def pprint_data(self, obj):
        return format_html("<pre>{}</pre>", pprint.pformat(obj.data, compact=True))

    pprint_inputs.short_description = "Inputs"
    pprint_data.short_description = "Data"


@admin.register(Judgement)
class JudgementAdmin(admin.ModelAdmin):
    list_display = ("title", "variable_name", "slug", "intervention")
    autocomplete_fields = [
        "intervention",
    ]
    search_fields = ["title", "intervention__title"]


@admin.register(Example)
class ExampleAdmin(admin.ModelAdmin):
    list_display = ("intervention", "title")
    list_filter = ("intervention",)
    autocomplete_fields = ["intervention"]
    search_fields = (
        "title",
        "intervention__title",
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
        """
        Renders a Mermaid diagram for the intervention.
        """
        # Generate Mermaid syntax for the diagram
        steps = obj.steps.all()
        transitions = Transition.objects.filter(
            Q(from_step__intervention=obj) | Q(to_step__intervention=obj)
        )

        diagram = ["graph TD"]
        for step in steps:
            diagram.append(f'{step.slug.replace("-", "_")}["{step.title}"]')

        for transition in transitions:
            from_slug = transition.from_step.slug.replace("-", "_")
            to_slug = transition.to_step.slug.replace("-", "_")
            conditions = transition.conditions or "No conditions set!!"
            # Escape quotes in conditions
            conditions = conditions.replace('"', "'")
            diagram.append(f'{from_slug} -->|"{conditions}"| {to_slug}')

        diagram.append(
            f"""classDef smallText fill:none,color:black,stroke:none, font-size:10px;linkStyle default stroke-width:1px,font-size:10px;"""
        )

        mermaid_code = "\n".join(diagram)

        # Render Mermaid container and script
        return mermaid_code

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
        return redirect(f"{settings.CHATBOT_URL}/?session_id={session.uuid}")

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
        "cycle__id",
        "state",
        "chatbot_link",
        "started",
        "last_updated",
        "uuid",
        # "clinical_notes",  # Add this to display related notes in the list view
    )
    list_filter = ("cycle__intervention__short_title", "started", "last_updated")
    search_fields = ("cycle__client__username",)
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

    def clinical_notes(self, obj):
        notes = Note.objects.filter(session_state__session=obj)
        if not notes.exists():
            return "No notes available"
        return format_html_join(
            "\n",
            "<p><strong>{}</strong>: {} ({})</p>",
            ((note.judgement.variable_name, note.val(), note.timestamp) for note in notes),
        )

    clinical_notes.short_description = "Clinical Notes/Judgements"

    def chatbot_link(self, obj):
        url = f"{settings.CHATBOT_URL}/?session_id={obj.uuid}"
        return format_html('<a href="{}" target="_blank">Continue</a>', url)

    chatbot_link.short_description = "Chat"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "start_again/<int:session_id>/<int:state_id>/",
                self.admin_site.admin_view(self.start_again_from_state),
                name="start_again",
            ),
        ]
        return custom_urls + urls

    def start_again_from_state(self, request, session_id, state_id):
        try:
            # Original session and state
            original_session = TreatmentSession.objects.get(id=session_id)
            original_state = TreatmentSessionState.objects.get(id=state_id)

            # 1. Duplicate the Cycle
            original_cycle = original_session.cycle
            new_cycle = Cycle.objects.create(
                client=original_cycle.client,
                intervention=original_cycle.intervention,
                start_date=original_session.cycles.start_date,
            )

            # 2. Duplicate the TreatmentSession
            new_session = TreatmentSession.objects.create(cycle=new_cycle, started=timezone.now())

            # 3. Duplicate relevant TreatmentSessionStates
            TreatmentSessionState.objects.filter(
                session=original_session, timestamp__lte=original_state.timestamp
            ).order_by("timestamp").update(session=new_session)

            # 4. Duplicate Turns and Notes before `state_id`
            turns_to_duplicate = Turn.objects.filter(
                session_state__session__cycle=original_session.cycle,
                session_state__timestamp__lte=original_state.timestamp,
            )
            for turn in turns_to_duplicate:
                turn.pk = None  # Reset primary key to create new object
                turn.session_state = new_session.state  # Attach to new session
                turn.save()

            notes_to_duplicate = Note.objects.filter(
                session_state__session__cycle=original_session.cycle,
                session_state__timestamp__lte=original_state.timestamp,
            )
            for note in notes_to_duplicate:
                note.pk = None
                note.session_state = new_session.state
                note.save()

            logging.warning(f"DUPLICATED SESSION {original_session} FROM STATE {original_state}")
            return redirect(f"{settings.CHATBOT_URL}/?session_id={new_session.uuid}")

        except Exception as e:
            self.message_user(
                request, f"An error occurred while starting again: {e}", level=messages.ERROR
            )
            return redirect("admin:app_treatmentsession_change", original_session.pk)

    def start_again_from_state(self, request, session_id, state_id):
        try:
            # Original session and state
            original_session = TreatmentSession.objects.get(id=session_id)
            original_state = TreatmentSessionState.objects.get(id=state_id)

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
                session=original_session, timestamp__lte=original_state.timestamp
            ).order_by("timestamp")
            for i in tss_to_dupe:
                i.pk = None
                i.session = new_session
                i.save()

            # 4. Duplicate Turns and Notes before `state_id`
            turns_to_duplicate = Turn.objects.filter(
                session_state__session=original_session,
                session_state__timestamp__lte=original_state.timestamp,
            )
            for turn in turns_to_duplicate:
                turn.pk = None  # Reset primary key to create new object
                turn.uuid = shortuuid.uuid()
                turn.session_state = new_session.state  # Attach to new session
                turn.save()

            notes_to_duplicate = Note.objects.filter(
                session_state__session=original_session,
                session_state__timestamp__lte=original_state.timestamp,
            )
            for note in notes_to_duplicate:
                note.pk = None
                note.uuid = shortuuid.uuid()
                note.session_state = new_session.state
                note.save()

            # Redirect to chatbot interface for the new session
            return redirect(f"{settings.CHATBOT_URL}/?session_id={new_session.uuid}")

        except Exception as e:
            logger.error(f"An error occurred while starting again: {e}")
            self.message_user(
                request, f"An error occurred while starting again: {e}", level=messages.ERROR
            )
            return redirect("admin:mindframe_treatmentsession_change", original_session.pk)
