# Generated by Django 5.1.3 on 2024-11-11 10:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mindframe", "0016_step_judgements_alter_stepjudgement_judgement"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="stepjudgement",
            options={"ordering": ["order"]},
        ),
        migrations.AddField(
            model_name="stepjudgement",
            name="once",
            field=models.BooleanField(
                default=False,
                help_text="Once we have a non-null value returned, don't repeat.",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="stepjudgement",
            unique_together={("judgement", "step", "when")},
        ),
    ]
