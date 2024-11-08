from django.contrib import admin
from django.db import models
from django.shortcuts import redirect
from django.urls import path
from django.utils.html import format_html
from django.utils import timezone
from django.conf import settings
from django.forms import Textarea

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
)


@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "role", "is_staff", "is_active")
    list_filter = ("role", "is_staff", "is_active")
    search_fields = ("username", "email")


class ExampleInline(admin.TabularInline):
    model = Example
    extra = 1


@admin.register(Cycle)
class CycleAdmin(admin.ModelAdmin):
    autocomplete_fields = ["intervention", "client"]
    list_display = ("start_date", "client", "intervention", "end_date")
    list_filter = ("start_date", "end_date")
    search_fields = ("client__username", "intervention__name")


class NoteInline(admin.TabularInline):
    model = Note
    extra = 1
    readonly_fields = ["judgement", "timestamp", "inputs", "data"]


class TreatmentSessionStateInline(admin.TabularInline):
    model = TreatmentSessionState
    extra = 0
    autocomplete_fields = ["step", "previous_step"]


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
    )
    list_filter = ("cycle__intervention__short_title", "started", "last_updated")
    search_fields = ("cycle__client__username",)
    inlines = [TreatmentSessionStateInline, NoteInline]

    def chatbot_link(self, obj):
        url = f"{settings.CHATBOT_URL}/?session_id={obj.uuid}"
        return format_html('<a href="{}" target="_blank">Continue</a>', url)

    chatbot_link.short_description = "Chat"


class TransitionInline(admin.TabularInline):
    model = Transition
    fk_name = "from_step"
    extra = 1
    autocomplete_fields = ("to_step",)

    formfield_overrides = {
        models.TextField: {
            "widget": admin.widgets.AdminTextareaWidget(
                attrs={"class": "transition-conditions"}
            )
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
    list_display = ("title", "intervention")
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
    list_display = ("session__id", "judgement", "val", "timestamp")
    list_filter = ("timestamp", "judgement")
    search_fields = ("session__cycle__client__username",)
    autocomplete_fields = [
        "session",
    ]


@admin.register(Judgement)
class JudgementAdmin(admin.ModelAdmin):
    autocomplete_fields = [
        "intervention",
    ]
    search_fields = ["title", "intervention__title"]


@admin.register(Example)
class ExampleAdmin(admin.ModelAdmin):
    list_display = ("intervention", "title")
    list_filter = ("intervention",)
    search_fields = (
        "title",
        "intervention__title",
    )


@admin.register(TreatmentSessionState)
class TreatmentSessionStateAdmin(admin.ModelAdmin):
    list_display = ("session", "step", "timestamp")


@admin.register(Intervention)
class InterventionAdmin(admin.ModelAdmin):
    list_display = ("title","slug", "short_title", "start_session_button")
    search_fields = ("title",)
    inlines = [ExampleInline]
    readonly_fields = ["slug"]

    def start_session_button(self, obj):
        return format_html(
            '<a class="button" href="{}">Start New Session</a>',
            f"start_session/{obj.id}/",
        )

    start_session_button.short_description = "Start Session"
    start_session_button.allow_tags = True

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "start_session/<int:intervention_id>/",
                self.admin_site.admin_view(self.start_session),
                name="start_session",
            ),
        ]
        return custom_urls + urls

    def start_session(self, request, intervention_id):
        intervention = Intervention.objects.get(pk=intervention_id)
        client = request.user
        cycle = Cycle.objects.create(intervention=intervention, client=client)
        session = TreatmentSession.objects.create(cycle=cycle, started=timezone.now())
        return redirect(f"{settings.CHATBOT_URL}/?session_id={session.uuid}")

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["start_session_action"] = format_html(
            '<a class="button" href="{}">Start New Session</a>',
            f"../start_session/{object_id}/",
        )
        return super().change_view(
            request, object_id, form_url, extra_context=extra_context
        )
