import logging
from django.conf import settings
from django.core.management.base import BaseCommand
from decouple import config
from mindframe.telegram import TelegramBotClient

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Manages the Telegram webhook with the provided bot token and webhook URL."

    def add_arguments(self, parser):
        parser.add_argument("--register", action="store_true", help="Register the Telegram webhook")
        parser.add_argument("--delete", action="store_true", help="Delete the Telegram webhook")
        parser.add_argument("--info", action="store_true", help="Get Telegram webhook info")

    def handle(self, *args, **kwargs):
        try:
            tgmb = TelegramBotClient(
                bot_name="MindframerBot",
                bot_secret_token=config("TELEGRAM_BOT_TOKEN", None),
                webhook_url=config("TELEGRAM_WEBHOOK_URL", None),
                webhook_validation_token=config("TELEGRAM_WEBHOOK_VALIDATION_TOKEN", None),
            )

            if kwargs["register"]:
                tgmb.setup_webhook()
                self.stdout.write("Webhook registered successfully.")
                self.stdout.write(f"Webhook URL: {tgmb.webhook_url}")

            elif kwargs["delete"]:
                tgmb.delete_webhook()
                self.stdout.write("Webhook deleted successfully.")

            elif kwargs["info"]:
                info = tgmb.get_webhook_info()
                self.stdout.write("Webhook Info:")
                self.stdout.write(str(info))

            else:
                self.stdout.write("Please provide one of --register, --delete, or --info flags.")

        except KeyError as e:
            self.stderr.write(f"Error: Missing required environment variables: {e}")

        except Exception as e:
            self.stderr.write(f"Unexpected error: {e}")
