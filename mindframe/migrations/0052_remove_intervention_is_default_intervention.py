# Generated by Django 5.2 on 2025-05-20 09:49

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("mindframe", "0051_rename_bot_identifier_botinterface_bot_name"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="intervention",
            name="is_default_intervention",
        ),
    ]
