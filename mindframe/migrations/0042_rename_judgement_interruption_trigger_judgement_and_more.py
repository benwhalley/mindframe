# Generated by Django 5.1.6 on 2025-03-21 11:09

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mindframe", "0041_alter_interruption_slug_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="interruption",
            old_name="judgement",
            new_name="trigger_judgement",
        ),
        migrations.AddField(
            model_name="interruption",
            name="resolution_judgement",
            field=models.ForeignKey(
                blank=True,
                help_text="If provided, this Judgement will be evaluated in every turn (so keep it simple). Whatever values it returns can be used in the resolution expression. If null, the resolution will be evaluated directly (using notes from other Judgements previously run).",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="interruption_resolutions",
                to="mindframe.judgement",
            ),
        ),
        migrations.AlterField(
            model_name="interruption",
            name="resolution",
            field=models.TextField(
                default="n_turns_step > 10 or interruption_resolved is True",
                help_text="In an interruption branch, Judgements should be used to (eventually) return a value which allows us to determine if the interruption should end. This `resolution` field is a condition that, if true, will jump the user back to their last checkpoint.",
            ),
        ),
    ]
