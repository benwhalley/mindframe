# Generated by Django 5.1.6 on 2025-03-14 12:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mindframe", "0033_remove_conversation_synthetic_client_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="turn",
            name="text_source",
        ),
        migrations.AlterField(
            model_name="turn",
            name="turn_type",
            field=models.CharField(
                choices=[
                    ("human", "Human utterance"),
                    ("bot", "Bot utterance"),
                    ("opening", "Fixed opening line"),
                    ("join", "Join"),
                ]
            ),
        ),
    ]
