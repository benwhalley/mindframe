# Generated by Django 5.1.3 on 2024-11-21 07:57

import django.db.models.deletion
import shortuuid.main
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mindframe", "0048_remove_llmlog_error_remove_llmlog_session_state_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="llmlog",
            name="traceback",
        ),
        migrations.AddField(
            model_name="llmlog",
            name="model",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="mindframe.llm",
            ),
        ),
    ]
