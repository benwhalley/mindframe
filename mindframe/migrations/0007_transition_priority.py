# Generated by Django 5.1.5 on 2025-02-10 14:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mindframe", "0006_turn_metadata"),
    ]

    operations = [
        migrations.AddField(
            model_name="transition",
            name="priority",
            field=models.PositiveSmallIntegerField(default=1),
        ),
    ]
