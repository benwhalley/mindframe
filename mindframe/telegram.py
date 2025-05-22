"""
TODO: Design decision about whether to capture system messages like response to /help etc
"""

import html
import ipaddress
import json
import logging
import traceback
from typing import Any, Dict, List, Optional, Tuple

import requests
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from telegram import Update

from mindframe.bot import (
    InboundMessage,
    MediaContent,
    MediaType,
    WebhookBotClient,
)
from mindframe.conversation import listen, respond
from mindframe.models import Conversation, CustomUser, Intervention, Referal

logger = logging.getLogger(__name__)

# Configuration constants
TELEGRAM_IP_RANGES = [ipaddress.ip_network(ip) for ip in ["149.154.160.0/20", "91.108.4.0/22"]]


class TelegramBotClient(WebhookBotClient):
    """
    Telegram implementation of the WebhookBotClient.
    """

    def __init__(self, **kwargs):
        """Initialize the Telegram bot client"""
        super().__init__(**kwargs)

    def setup_webhook(self) -> bool:
        """
        Setup the webhook for this client on Telegram.
        Returns True if successful, False otherwise.
        """
        if not self.webhook_validation_token:
            raise Exception("Must set a validation token for telegram webhooks")

        try:
            url = f"https://api.telegram.org/bot{self.bot_secret_token}/setWebhook"
            data = {"url": self.webhook_url, "secret_token": self.webhook_validation_token}
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            logger.info(response)
            logger.info("Telegram webhook set up successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to set up Telegram webhook: {e}")
            return False

    def get_webhook_info(self) -> Dict[str, Any]:

        get_info_url = f"https://api.telegram.org/bot{self.bot_secret_token}/getWebhookInfo"
        response = requests.get(get_info_url)
        try:
            return json.loads(response.content)
        except Exception as e:
            logger.error(f"Failed to get webhook info: {e}")
            return {"error": str(e)}

    def delete_webhook(self) -> bool:
        """
        Delete the webhook for this client on Telegram.
        Returns True if successful, False otherwise.
        """

        try:
            url = f"https://api.telegram.org/bot{self.bot_secret_token}/deleteWebhook"
            data = {"url": self.webhook_url, "secret_token": self.webhook_validation_token}
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            logger.info(response)
            logger.info("Telegram webhook deleted successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to delete Telegram webhook: {e}")
            return False

    def validate_request(self, request) -> bool:
        """
        Validate that an incoming request is authentic and from Telegram.
        """
        # Validate IP address
        client_ip = request.META.get("HTTP_X_FORWARDED_FOR") or request.META.get("REMOTE_ADDR")
        ip = ipaddress.ip_address(client_ip)
        valid_ip = any(ip in net for net in TELEGRAM_IP_RANGES)

        # Validate token in header
        if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != self.webhook_validation_token:
            valid_header = False
        else:
            valid_header = True

        logger.info(
            f"Telegram request validation - Valid IP: {valid_ip}, valid header: {valid_header}"
        )
        return valid_ip and valid_header

    def parse_message(self, request) -> InboundMessage:
        """
        Parse the incoming message from Telegram's format into a standard InboundMessage.
        """
        try:
            # Parse the raw update from Telegram
            update = Update.de_json(json.loads(request.body))

            if not update.message:
                raise ValueError("No message found in update")

            message = update.message
            user_data = message.from_user

            # Extract media information if present
            media_list = []

            # Check for photo
            if message.photo:
                raise NotImplementedError("Photos not handled yet")
                # Get largest photo (last in array)
                photo = message.photo[-1]
                media_list.append(
                    MediaContent(
                        type=MediaType.IMAGE,
                        url="",  # Telegram doesn't provide direct URLs
                        file_id=photo.file_id,
                        file_size=photo.file_size,
                        caption=message.caption,
                    )
                )

            # Check for document
            if message.document:
                raise NotImplementedError("Documnets not handled yet")
                media_list.append(
                    MediaContent(
                        type=MediaType.DOCUMENT,
                        url="",
                        file_id=message.document.file_id,
                        mime_type=message.document.mime_type,
                        file_size=message.document.file_size,
                        file_name=message.document.file_name,
                    )
                )

            # Check for audio
            if message.audio:
                media_list.append(
                    MediaContent(
                        type=MediaType.AUDIO,
                        url="",
                        file_id=message.audio.file_id,
                        mime_type=message.audio.mime_type,
                        file_size=message.audio.file_size,
                        duration=message.audio.duration,
                        file_name=message.audio.file_name,
                    )
                )

            # Check for video notes
            if message.video_note:
                media_list.append(
                    MediaContent(
                        type=MediaType.VIDEO,
                        url="",
                        file_id=message.video_note.file_id,
                        file_size=message.video_note.file_size,
                        duration=message.video_note.duration,
                    )
                )

            # Check for voice
            if message.voice:
                media_list.append(
                    MediaContent(
                        type=MediaType.VOICE,
                        url="",
                        file_id=message.voice.file_id,
                        mime_type=message.voice.mime_type,
                        file_size=message.voice.file_size,
                        duration=message.voice.duration,
                    )
                )

            # Create the standardized message
            inbound_message = InboundMessage(
                platform="telegram",
                platform_user_id=str(user_data.id),
                chat_id=str(message.chat.id),
                message_id=str(message.message_id),
                text=message.text or message.caption or "",
                reply_to_message_id=(
                    str(message.reply_to_message.message_id) if message.reply_to_message else None
                ),
                timestamp=message.date.timestamp() if message.date else None,
                media=media_list,
                reaction=None,  # Telegram reactions need more processing
                raw_data=update.to_dict(),  # Store the full update for reference
            )

            return inbound_message

        except Exception as e:
            logger.error(f"Error parsing Telegram message: {e}")
            raise ValueError(f"Failed to parse Telegram message: {e}")

    def audio_to_text(self, message):
        pass

    def get_or_create_user(self, message: InboundMessage) -> CustomUser:
        """
        Get or create a user based on the Telegram user ID.
        """
        user_id = message.platform_user_id
        raw_data = message.raw_data

        # Extract user info from raw data
        from_user = raw_data.get("message", {}).get("from", {})
        first_name = from_user.get("first_name", "")
        last_name = from_user.get("last_name", "")

        # Create or get the user
        user, created = CustomUser.objects.get_or_create(
            username=f"telegram_user_{user_id}",
            defaults={
                "first_name": first_name,
                "last_name": last_name,
            },
        )

        # Update user info if it changed
        # TODO: make this cover more fields
        if not created and (user.first_name != first_name or user.last_name != last_name):
            user.first_name = first_name
            user.last_name = last_name
            user.save(update_fields=["first_name", "last_name"])

        return user

    def get_or_create_conversation(
        self, message: InboundMessage, intervention=None
    ) -> Tuple[Any, bool]:
        """
        Get or create a conversation for this chat.
        Initialises the conversation if it doesn't exist already with the user and intervention.
        """
        conversation, is_new = Conversation.objects.get_or_create(
            chat_room_id=message.chat_id, archived=False, bot_interface=self.bot_interface
        )
        user = self.get_or_create_user(message)
        if is_new:
            self._initialise_new_conversation(
                conversation, intervention or self.intervention, user, message.chat_id
            )
        return conversation, is_new

    def format_message(self, text: str) -> str:
        """
        Format a message for Telegram (handles HTML formatting).
        """
        # Telegram supports HTML by default
        # TODO: might want to add more sophisticated formatting here
        return html.escape(text)

    def send_message(self, chat_id: str, text: str) -> bool:
        """
        Send a message to Telegram.
        """
        logger.info(f"Attempting to send text to telegram chat {chat_id}: \n{text}\n")
        text = self.format_message(text)

        if text.strip() == "":
            logger.warning("Message text is empty. Not sending.")
            return False

        try:
            url = f"https://api.telegram.org/bot{self.bot_secret_token}/sendMessage"
            data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            logger.error(str(response.content))
            logger.error(traceback.format_exc())
            return False

    def send_typing_indicator(self, chat_id: str) -> bool:
        """
        Send a typing indicator to Telegram.
        """
        try:
            url = f"https://api.telegram.org/bot{self.bot_secret_token}/sendChatAction"
            data = {"chat_id": chat_id, "action": "typing"}

            response = requests.post(url, data=data, timeout=5)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.warning(f"Failed to send typing indicator: {e}")
            return False

    def handle_command(
        self, message: InboundMessage, conversation, request
    ) -> Tuple[Optional[HttpResponse], Optional[str]]:
        """
        Handle Telegram-specific commands.
        """
        # Command handler mapping
        command_handlers = {
            "start": self.handle_start_command,
            "help": self.handle_help_command,
            "new": self.handle_new_command,
            "clear": self.handle_clear_command,
            "settings": self.handle_settings_command,
            "web": self.handle_web_command,
            "list": self.handle_list_command,
            "undo": self.handle_undo_command,
        }

        if message.command in command_handlers:
            return command_handlers[message.command](
                message.command_args, message, conversation, request
            )

        # If command not recognized, return a message about unknown command
        return None, f"Unknown command: /{message.command}. Type /help for available commands."

    def handle_help_command(
        self, args: List[str], message: InboundMessage, conversation, request
    ) -> Tuple[Optional[HttpResponse], str]:
        """
        Help command implementation for Telegram.
        """
        help_text = (
            "Commands:\n"
            "/clear - start a fresh conversation\n"
            "/new <bot_name> - start a new conversation with a specific bot\n"
            "/help - show this message\n"
            "/settings - show settings\n"
            "/web - show web page link for this conversation\n"
            "/list - list available interventions\n"
            "/undo [n] - undo last n turns or a specific turn by UUID"
        )
        return None, help_text

    def handle_start_command(
        self, args: List[str], message: InboundMessage, conversation, request
    ) -> Tuple[Optional[HttpResponse], Optional[str]]:
        """
        Start a new conversation with the specified intervention.
        """
        if not args:
            logger.info(f"No args for start command: {args}")
            return (
                None,
                "...",
            )
        token = args[0].strip()
        referal = Referal.objects.get(uuid=token)

        conversation.archived = True
        conversation.save()

        conversation = referal.conversation
        conversation.chat_room_id = message.chat_id
        conversation.save()

        self.send_message(message.chat_id, "Using referal code ...")
        return JsonResponse({"status": "ok"}, status=200), None

    def handle_new_command(
        self, args: List[str], message: InboundMessage, conversation, request
    ) -> Tuple[Optional[HttpResponse], Optional[str]]:
        """
        Start a new conversation with the specified intervention.
        """
        if not args:
            return (
                None,
                "Please specify an intervention slug. Use /list to see available interventions.",
            )

        slug = args[0].strip()

        try:
            # Get the intervention
            intervention = get_object_or_404(Intervention, slug=slug)
            logger.info(f"Started new conversation using {intervention}")
            conversation.archived = True
            conversation.save()

            self.send_message(
                message.chat_id,
                f"Starting a new conversation with {intervention.title}. \n\nForgetting everything we talked about so far)...",
            )

            new_conversation, _ = self.get_or_create_conversation(
                message, intervention=intervention
            )

            return JsonResponse({"status": "ok"}, status=200), None

        except Exception as e:
            logger.error(f"Error starting new conversation: {e}")
            available = ", ".join(Intervention.objects.all().values_list("slug", flat=True))
            return (
                None,
                f"Error starting intervention. Available interventions: {available}",
            )

    def handle_clear_command(
        self, args: List[str], message: InboundMessage, conversation
    ) -> Tuple[Optional[HttpResponse], Optional[str]]:
        """
        Start a new conversation with the specified intervention.
        """

        try:

            conversation.archived = True
            conversation.save()
            self.send_message(
                message.chat_id,
                "Starting a new conversation (forgetting everything we talked about so far).",
            )

            new_conversation, _ = self.get_or_create_conversation(message)

            return JsonResponse({"status": "ok"}, status=200), None

        except Exception as e:
            logger.error(f"Error starting new conversation: {e}")
            available = ", ".join(Intervention.objects.all().values_list("slug", flat=True))
            return (
                None,
                f"Error starting intervention. Available interventions: {available}",
            )

    def handle_settings_command(
        self, args: List[str], message: InboundMessage, conversation, request
    ) -> Tuple[Optional[HttpResponse], str]:
        """
        Settings command implementation for Telegram.
        """
        # For now, just return a message that no settings are available
        return None, "No settings available at this time."

    # METHODS TO ACTUALLY HANDLE USER INPUT
    def process_webhook(self, request) -> HttpResponse:
        """Process an incoming webhook request from Telegram."""

        try:
            message = self.parse_message(request)
            user = self.get_or_create_user(message)
            conversation, is_new = self.get_or_create_conversation(message)

            if message.command:
                response, reply_text = self.handle_command(message, conversation, request)
                if response is not None:
                    return response
                if reply_text is not None:
                    self.send_message(message.chat_id, reply_text)
                    return HttpResponse("OK", status=200)

            else:  # Process normal message flow
                self.process_webhook_message(message)
        except Exception as e:
            logger.error(f"Error processing inbound request: {e}\n{request}")
            logger.error(traceback.format_exc())
        return HttpResponse("OK", status=200)

    def process_webhook_message(self, message: InboundMessage):
        """Process a normal message from a webhook client

        TODO: handle reactions
        """

        user = self.get_or_create_user(message)
        conversation, is_new = self.get_or_create_conversation(message)

        if is_new:
            # Send welcome message for new conversations
            self.send_message(message.chat_id, "Welcome to the bot!")
        else:
            # Continue existing conversation
            self.continue_webhook_conversation(user, conversation, message)

    def continue_webhook_conversation(self, user, conversation, message: InboundMessage):
        """Continue an existing conversation for a webhook client"""
        self.send_typing_indicator(message.chat_id)
        logger.info(f"Continuing conversation {conversation.uuid} with user {user.username}")
        turn_to_respond_to = conversation.turns.all().last()
        user_turn = listen(turn_to_respond_to, message.text, user)
        bot_turn = respond(user_turn)
        self.send_message(message.chat_id, bot_turn.text)
