# Generated by Django 5.1.5 on 2025-02-11 11:31

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mindframe", "0010_step_opening_line_alter_turn_text_source"),
    ]

    operations = [
        migrations.CreateModel(
            name="OfflineStepJudgement",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "judgement",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="offlinestepjudgements",
                        to="mindframe.judgement",
                    ),
                ),
                (
                    "step",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="offlinestepjudgements",
                        to="mindframe.step",
                    ),
                ),
            ],
            options={
                "unique_together": {("judgement", "step")},
            },
        ),
        migrations.AddField(
            model_name="step",
            name="offline_judgements",
            field=models.ManyToManyField(
                related_name="offline_judgements",
                through="mindframe.OfflineStepJudgement",
                to="mindframe.judgement",
            ),
        ),
    ]
