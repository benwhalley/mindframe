import os
import requests
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from decouple import config

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Registers the Telegram webhook with the provided bot token and webhook URL."

    def handle(self, *args, **kwargs):
        TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
        TELEGRAM_WEBHOOK_URL = config("TELEGRAM_WEBHOOK_URL")
        TELEGRAM_WEBHOOK_VALIDATION_TOKEN = config("TELEGRAM_WEBHOOK_VALIDATION_TOKEN")

        if (
            not TELEGRAM_BOT_TOKEN
            or not TELEGRAM_WEBHOOK_URL
            or not TELEGRAM_WEBHOOK_VALIDATION_TOKEN
        ):
            self.stderr.write("Error: Missing required environment variables.")
            return

        delete_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook"
        setup_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
        get_info_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo"

        try:
            # Delete existing webhook
            response = requests.post(delete_url)
            response.raise_for_status()
            self.stdout.write("Deleted existing webhook.")

            # Set new webhook
            data = {
                "url": TELEGRAM_WEBHOOK_URL,
                "secret_token": TELEGRAM_WEBHOOK_VALIDATION_TOKEN,
            }
            response = requests.post(setup_url, data=data)
            response.raise_for_status()
            self.stdout.write("Successfully registered new Telegram webhook.")

            # Get webhook status
            response = requests.get(get_info_url)
            response.raise_for_status()
            self.stdout.write(f"Webhook status: {response.json()}")

        except requests.RequestException as e:
            self.stderr.write(f"Failed to register webhook: {e}")
