from decouple import config
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from llmtools.models import LLM, LLMCredentials
from mindframe.settings import RESERVED_USERNAMES

User = get_user_model()


class Command(BaseCommand):
    help = "Ensures default system objects exsit, e.g. users system, therapist, client, LLM and credentials."

    def handle(self, *args, **options):
        usernames = RESERVED_USERNAMES
        for username in usernames:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": f"{username}@example.com",
                    "is_active": True,
                },
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created user: {username}"))

        llmc, created = LLMCredentials.objects.get_or_create(
            pk=1,
            defaults={
                "label": "Default credentials",
                "llm_api_key": config("LITELLM_API_KEY", default="XXXXXXXX"),
                "llm_base_url": config("LITELLM_ENDPOINT", default="https://example.com"),
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created default LLM credentials"))
            if not config("LITELLM_API_KEY", default=None) or not config(
                "LITELLM_ENDPOINT", default=None
            ):
                self.stdout.write(
                    self.style.WARNING(
                        f"No keys found for LLM credentials. Set LITELLM_API_KEY and LITELLM_ENDPOINT in .env"
                    )
                )

        llmd, created = LLM.objects.get_or_create(
            pk=1,
            defaults={
                "model_name": "gpt-4o-mini",
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created default LLM model as gpt-4o-mini"))
