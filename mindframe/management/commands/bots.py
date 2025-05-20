import logging

from decouple import config
from django.conf import settings
from django.core.management.base import BaseCommand

from mindframe.models import BotInterface

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Manages the Telegram webhook with the provided bot token and webhook URL."

    def add_arguments(self, parser):
        parser.add_argument("--register", action="store_true", help="Register the Telegram webhook")
        parser.add_argument("--delete", action="store_true", help="Delete the Telegram webhook")
        parser.add_argument("--info", action="store_true", help="Get Telegram webhook info")

    def handle(self, *args, **kwargs):

        for obj in BotInterface.objects.all():
            try:
                bot_client = obj.bot_client()

                if kwargs["register"]:
                    bot_client.setup_webhook()
                    self.stdout.write("Webhook registered successfully.")
                    self.stdout.write(f"Webhook URL: {bot_client.webhook_url}")

                elif kwargs["delete"]:
                    bot_client.delete_webhook()
                    self.stdout.write("Webhook deleted successfully.")

                elif kwargs["info"]:
                    info = bot_client.get_webhook_info()
                    self.stdout.write("Webhook Info:")
                    self.stdout.write(str(info))

                else:
                    self.stdout.write(
                        "Please provide one of --register, --delete, or --info flags."
                    )

            except KeyError as e:
                self.stderr.write(f"Error: Missing required environment variables: {e}")

            except Exception as e:
                self.stderr.write(f"Unexpected error: {e}")
