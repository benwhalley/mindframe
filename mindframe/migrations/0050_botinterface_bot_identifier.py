# Generated by Django 5.2 on 2025-05-20 08:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mindframe", "0049_botinterface"),
    ]

    operations = [
        migrations.AddField(
            model_name="botinterface",
            name="bot_identifier",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
