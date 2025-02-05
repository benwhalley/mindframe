# Generated by Django 5.1.5 on 2025-01-30 14:31

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("llmtools", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ToolKey",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("tool_key", models.UUIDField(default=uuid.uuid4, unique=True)),
                (
                    "tool",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tool_keys",
                        to="llmtools.tool",
                    ),
                ),
            ],
        ),
    ]
