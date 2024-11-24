# Generated by Django 5.1.3 on 2024-11-20 17:06

import django.db.models.deletion
import shortuuid.main
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mindframe", "0043_llm_alter_note_uuid_alter_treatmentsession_uuid_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="intervention",
            name="default_conversation_model",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="default_for_conversations",
                to="mindframe.llm",
            ),
        ),
        migrations.AddField(
            model_name="intervention",
            name="default_judgement_model",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="default_for_judgements",
                to="mindframe.llm",
            ),
        ),
    ]