# Generated by Django 5.1.3 on 2024-11-08 14:31

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("mindframe", "0006_turn_session_state"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="turn",
            name="session",
        ),
    ]