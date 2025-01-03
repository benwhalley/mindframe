# Generated by Django 5.1.3 on 2024-11-12 08:52

import django.db.models.deletion
import mindframe.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mindframe", "0024_intervention_slug_alter_note_uuid_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="note",
            name="session_state",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="notes",
                to="mindframe.treatmentsessionstate",
            ),
        ),
        migrations.AlterField(
            model_name="note",
            name="session",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="notes_old",
                to="mindframe.treatmentsession",
            ),
        ),
    ]
