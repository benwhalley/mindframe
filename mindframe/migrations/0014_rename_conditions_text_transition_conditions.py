# Generated by Django 5.1.3 on 2024-11-11 08:13

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("mindframe", "0013_remove_transition_conditions"),
    ]

    operations = [
        migrations.RenameField(
            model_name="transition",
            old_name="conditions_text",
            new_name="conditions",
        ),
    ]