# Generated by Django 5.1.3 on 2024-12-05 13:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mindframe", "0061_remove_example_example_embedding_index_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="llm",
            name="nickname",
        ),
        migrations.RemoveField(
            model_name="llm",
            name="provider_name",
        ),
        migrations.AlterField(
            model_name="llm",
            name="model_name",
            field=models.CharField(
                help_text="Litellm model name, e.g. llama3.2 or azure/gpt-4o", max_length=255
            ),
        ),
    ]
