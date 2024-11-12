# Generated by Django 5.1.3 on 2024-11-11 08:10

import django.db.models.deletion
import mindframe.models
from django.conf import settings
from django.db import migrations, models

import shortuuid


def generate_short_uuid():
    return shortuuid.uuid().lower()


class Migration(migrations.Migration):

    dependencies = [
        ("mindframe", "0010_alter_treatmentsession_uuid"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="transition",
            name="judgements",
        ),
        migrations.AddField(
            model_name="transition",
            name="conditions_text",
            field=models.TextField(
                blank=True,
                help_text="Python code to evaluate before the transition can be be made. Each line is evaluated indendently and all must be True for the transition to be made. Variables created by Judgements are passed in as a dictionary.",
            ),
        ),
        migrations.AlterField(
            model_name="cycle",
            name="client",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="cycles",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="treatmentsession",
            name="uuid",
            field=models.CharField(
                default=generate_short_uuid,
                editable=False,
                unique=True,
            ),
        ),
        migrations.AlterField(
            model_name="turn",
            name="session_state",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="turns",
                to="mindframe.treatmentsessionstate",
            ),
        ),
        migrations.CreateModel(
            name="StepJudgement",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "when",
                    models.CharField(
                        choices=[
                            ("turn", "Each turn"),
                            ("enter", "When entering the step"),
                            ("exit", "When exiting the step"),
                        ],
                        default="turn",
                        max_length=10,
                    ),
                ),
                (
                    "judgement",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="step_judgements",
                        to="mindframe.judgement",
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="step",
            name="judgements",
            field=models.ManyToManyField(related_name="steps", to="mindframe.stepjudgement"),
        ),
    ]
