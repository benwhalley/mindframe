# Generated by Django 5.1.5 on 2025-02-12 20:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "mindframe",
            "0015_rename_telegram_conversation_user_conversation_telegram_conversation_id",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="conversation",
            name="archived",
            field=models.BooleanField(default=False),
        ),
    ]
