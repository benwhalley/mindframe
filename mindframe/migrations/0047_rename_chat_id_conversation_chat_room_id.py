# Generated by Django 5.1.6 on 2025-03-31 10:55

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("mindframe", "0046_rename_chat_room_id_conversation_chat_id"),
    ]

    operations = [
        migrations.RenameField(
            model_name="conversation",
            old_name="chat_id",
            new_name="chat_room_id",
        ),
    ]
