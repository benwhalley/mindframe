# Generated by Django 5.1.5 on 2025-02-13 21:22

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mindframe", "0024_remove_intervention_default_fake_client_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="conversation",
            name="default_fake_client",
        ),
        migrations.AddField(
            model_name="conversation",
            name="synthetic_client",
            field=models.ForeignKey(
                blank=True,
                help_text="Default intervention to choose as a partner when creating a new Synthetic conversation turns",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="mindframe.intervention",
            ),
        ),
    ]
