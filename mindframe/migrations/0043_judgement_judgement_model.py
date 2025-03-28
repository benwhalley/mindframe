# Generated by Django 5.1.6 on 2025-03-21 11:13

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mindframe", "0042_rename_judgement_interruption_trigger_judgement_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="judgement",
            name="judgement_model",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="used_for_judgements",
                to="mindframe.llm",
            ),
        ),
    ]
