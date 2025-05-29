from django.contrib import admin
from django.shortcuts import redirect

from .models import LLM, Job, JobGroup, LLMCredentials


@admin.register(LLM)
class LLMAdmin(admin.ModelAdmin):
    search_fields = ["model_name"]
    list_display = [
        "model_name",
    ]


@admin.register(LLMCredentials)
class LLMCredentialsAdmin(admin.ModelAdmin):
    search_fields = ["label"]


class JobInline(admin.TabularInline):
    model = Job
    extra = 0


class JobGroupAdmin(admin.ModelAdmin):
    inlines = [JobInline]
    list_display = ["tool", "owner", "status", "complete", "cancelled"]
    list_filter = ["owner", "cancelled"]


admin.site.register(JobGroup, JobGroupAdmin)

from .models import Tool, ToolKey

# Register your models here.


@admin.register(Tool)
class ToolAdmin(admin.ModelAdmin):
    list_display = ["name"]

    def response_change(self, request, obj):
        return redirect(obj.get_absolute_url())


@admin.register(ToolKey)
class ToolKeyAdmin(admin.ModelAdmin):
    pass
