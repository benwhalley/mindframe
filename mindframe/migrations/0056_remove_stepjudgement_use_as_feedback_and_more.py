# Generated by Django 5.1.3 on 2024-11-22 09:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mindframe", "0055_alter_note_uuid_alter_treatmentsession_uuid_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="stepjudgement",
            name="use_as_feedback",
        ),
        migrations.AddField(
            model_name="stepjudgement",
            name="use_as_guidance",
            field=models.BooleanField(
                default=False,
                help_text="Allow this judgement to be used as guidance when generating responses to the client. Exposed as a list of {{guidance}} in the prompt template.",
            ),
        ),
    ]
