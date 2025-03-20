# Generated by Django 5.1.6 on 2025-03-20 16:13

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mindframe", "0038_alter_interruption_judgement"),
    ]

    operations = [
        migrations.AddField(
            model_name="turn",
            name="resuming_from",
            field=models.ForeignKey(
                blank=True,
                help_text="The checkpoint Turn from which this Turn is resuming.",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="resumed_at",
                to="mindframe.turn",
            ),
        ),
        migrations.AlterField(
            model_name="interruption",
            name="intervention",
            field=models.ForeignKey(
                help_text="The intervention to which this interruption belongs.",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="interruptions",
                to="mindframe.intervention",
            ),
        ),
        migrations.AlterField(
            model_name="interruption",
            name="judgement",
            field=models.ForeignKey(
                blank=True,
                help_text="If provided, this Judgement will be evaluated before the trigger. Whatever values it returns can be used in the trigger expression. If null, the trigger will be evaluated directly (using notes from other Judgements previously run).",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="interruptions",
                to="mindframe.judgement",
            ),
        ),
        migrations.AlterField(
            model_name="interruption",
            name="target_step",
            field=models.ForeignKey(
                help_text="The step to switch to if the interruption is triggered.",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="interruptions",
                to="mindframe.step",
            ),
        ),
        migrations.AlterField(
            model_name="interruption",
            name="trigger",
            field=models.TextField(
                default="interrupt is True",
                help_text="An expression to decide if the Interruption should be triggered. If using the default value, a Judgement should have returned a value for `interrupt` which is boolean (or coercible to boolean). If interrupt is True, the interruption will be triggered and the conversation will switch to the target step.",
            ),
        ),
    ]
