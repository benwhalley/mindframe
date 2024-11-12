# Generated by Django 5.1.3 on 2024-11-11 14:57

import autoslug.fields
import mindframe.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mindframe", "0023_alter_note_uuid_alter_treatmentsession_uuid_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="intervention",
            name="slug",
            field=autoslug.fields.AutoSlugField(
                default="fit", editable=False, populate_from="short_title", unique=True
            ),
            preserve_default=False,
        ),
    ]
