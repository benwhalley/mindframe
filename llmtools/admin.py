from django.contrib import admin

from .models import Tool, ToolKey

# Register your models here.


@admin.register(Tool)
class ToolAdmin(admin.ModelAdmin):
    list_display = ["name", "get_absolute_url"]


@admin.register(ToolKey)
class ToolKeyAdmin(admin.ModelAdmin):
    pass
