from django.contrib import admin
from django.shortcuts import redirect

from .models import Job, JobGroup


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
