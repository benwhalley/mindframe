# Generated by Django 5.1.5 on 2025-02-11 14:51

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mindframe", "0012_alter_judgement_unique_together_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="step",
            name="offline_judgements",
        ),
        migrations.AddField(
            model_name="intervention",
            name="default_fake_client",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="mindframe.intervention",
            ),
        ),
        migrations.AlterField(
            model_name="stepjudgement",
            name="when",
            field=models.CharField(
                choices=[
                    ("turn", "Each turn"),
                    ("enter", "When entering the step"),
                    ("exit", "When exiting the step"),
                    (
                        "offline",
                        "After each turn asyncronously, probably available for the next turn",
                    ),
                ],
                default="turn",
                max_length=10,
            ),
        ),
        migrations.DeleteModel(
            name="OfflineStepJudgement",
        ),
    ]
