# Generated by Django 5.1.3 on 2024-11-21 15:06

import django.db.models.deletion
import shortuuid.main
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mindframe", "0051_alter_note_uuid_alter_treatmentsession_uuid_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="llmlog",
            name="turn",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="mindframe.turn",
            ),
        ),
    ]
