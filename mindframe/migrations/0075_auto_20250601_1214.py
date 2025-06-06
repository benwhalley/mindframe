# Generated by Django 5.2 on 2025-06-01 11:14

from django.db import migrations


def set_default_usage_plan(apps, schema_editor):
    BotInterface = apps.get_model("mindframe", "BotInterface")
    UsagePlan = apps.get_model("mindframe", "UsagePlan")

    default_plan = UsagePlan._default_manager.order_by("id").first()
    BotInterface._default_manager.filter(default_usage_plan__isnull=True).update(
        default_usage_plan=default_plan
    )


class Migration(migrations.Migration):

    dependencies = [
        ("mindframe", "0074_alter_conversation_options_and_more"),
    ]

    operations = [
        migrations.RunPython(set_default_usage_plan, reverse_code=migrations.RunPython.noop),
    ]
