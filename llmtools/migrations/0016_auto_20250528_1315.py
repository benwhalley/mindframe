import django.db.models.deletion
from django.db import migrations, models


def create_default_llm_and_credentials(apps, schema_editor):
    LLM = apps.get_model("llmtools", "LLM")
    LLMCredentials = apps.get_model("llmtools", "LLMCredentials")

    creds, _ = LLMCredentials.objects.get_or_create(
        pk=1,
        defaults={
            "label": "Default credentials",
            "llm_api_key": "dummy-key",
            "llm_base_url": "https://example.com",  # or whatever your default is
        },
    )

    LLM.objects.get_or_create(
        pk=1,
        defaults={
            "model_name": "gpt-4o",
            "credentials": creds,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("llmtools", "0015_llmcredentials_label"),  # or whatever the previous migration is
    ]

    operations = [
        migrations.AlterField(
            model_name="tool",
            name="model",
            field=models.ForeignKey(
                help_text="The LLM to use for this Tool",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="llmtools.llm",
            ),
        ),
        migrations.AddField(
            model_name="llmcredentials",
            name="label",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.RunPython(
            create_default_llm_and_credentials, reverse_code=migrations.RunPython.noop
        ),
    ]
