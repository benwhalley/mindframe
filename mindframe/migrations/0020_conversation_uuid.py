# Generated by Django 5.1.5 on 2025-02-13 09:03

from django.db import migrations

import mindframe.shortuuidfield


class Migration(migrations.Migration):

    dependencies = [
        ("mindframe", "0019_alter_conversation_unique_together"),
    ]

    operations = [
        migrations.AddField(
            model_name="conversation",
            name="uuid",
            field=mindframe.shortuuidfield.MFShortUUIDField(
                blank=True, editable=False, max_length=27
            ),
        ),
    ]
