# Generated by Django 5.1.5 on 2025-02-10 00:46

from django.db import migrations

import mindframe.shortuuidfield


class Migration(migrations.Migration):

    dependencies = [
        ("mindframe", "0003_alter_note_uuid_alter_turn_uuid"),
    ]

    operations = [
        migrations.AlterField(
            model_name="note",
            name="uuid",
            field=mindframe.shortuuidfield.MFShortUUIDField(
                blank=True, editable=False, max_length=27, unique=True
            ),
        ),
        migrations.AlterField(
            model_name="turn",
            name="uuid",
            field=mindframe.shortuuidfield.MFShortUUIDField(
                blank=True, editable=False, max_length=27, unique=True
            ),
        ),
    ]
