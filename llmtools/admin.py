from django.contrib import admin
from .models import JobGroup, Job


class JobInline(admin.TabularInline):
    model = Job
    extra = 0


class JobGroupAdmin(admin.ModelAdmin):
    inlines = [JobInline]


admin.site.register(JobGroup, JobGroupAdmin)

from .models import Tool, ToolKey

# Register your models here.


@admin.register(Tool)
class ToolAdmin(admin.ModelAdmin):
    list_display = ["name", "get_absolute_url"]


@admin.register(ToolKey)
class ToolKeyAdmin(admin.ModelAdmin):
    pass
