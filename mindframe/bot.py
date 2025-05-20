import asyncio
import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from django.http import HttpResponse
from django.urls import reverse

from mindframe.conversation import conversation_history, initialise_new_conversation
from mindframe.models import Intervention
from mindframe.settings import BranchReasons
from mindframe.tree import create_branch

logger = logging.getLogger(__name__)


class ClientType(Enum):
    """Enum for different types of client implementations"""

    WEBHOOK = auto()  # Client receives updates via webhooks (Telegram, Slack)
    CONNECTION = auto()  # Client maintains persistent connection (Matrix)


class MediaType(Enum):
    """Enum for different types of media that can be attached to a message"""

    AUDIO = "audio"
    VIDEO = "video"
    IMAGE = "image"
    DOCUMENT = "document"
    VOICE = "voice"


@dataclass
class MediaContent:
    """Class to represent media content attached to a message"""

    type: MediaType
    url: str
    file_id: str = ""
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    duration: Optional[int] = None  # For audio/video in seconds
    file_name: Optional[str] = None
    caption: Optional[str] = None


@dataclass
class ReactionContent:
    """Class to represent a reaction to a message"""

    emoji: str
    user_id: str
    message_id: str


@dataclass
class InboundMessage:
    """Standardized format for incoming messages from any platform"""

    platform: str  # e.g., "telegram", "slack", "matrix"
    platform_user_id: str  # User ID specific to the platform
    chat_id: str  # Chat/room/channel ID
    message_id: str = ""  # Platform-specific message ID
    text: str = ""  # Message text content
    reply_to_message_id: Optional[str] = None  # ID of message this is replying to
    timestamp: Optional[float] = None  # Unix timestamp when message was sent
    media: List[MediaContent] = field(default_factory=list)  # Attached media
    reaction: Optional[ReactionContent] = None  # Reaction if this is a reaction event
    raw_data: Dict = field(default_factory=dict)  # Raw platform data for reference

    @property
    def has_text(self) -> bool:
        """Check if the message has non-empty text content"""
        return bool(self.text and self.text.strip())

    @property
    def has_media(self) -> bool:
        """Check if the message has any media attached"""
        return len(self.media) > 0

    @property
    def is_reaction(self) -> bool:
        """Check if the message is a reaction"""
        return self.reaction is not None

    @property
    def command(self) -> Optional[str]:
        """Extract command from message if it starts with / or ?"""
        if not self.has_text:
            return None

        # TODO - more validation if this is a valid command and not
        # just a message starting with "/" or "?"
        text = self.text.strip()
        if text.startswith("/") or text.startswith("?"):
            parts = text.split(maxsplit=1)
            return parts[0][1:]  # Remove the prefix (/ or ?)
        return None

    @property
    def command_args(self) -> List[str]:
        """Extract command arguments if this is a command"""
        if not self.command:
            return []
        parts = self.text.strip().split(maxsplit=1)
        return parts[1:] if len(parts) > 1 else []


class MindframeBotClient(ABC):
    """
    Abstract base class for bot clients.
    Base class with common functionality for all clients.
    """

    def __init__(self):
        """Initialize the bot client"""
        pass

    @abstractmethod
    def get_or_create_user(self, message: InboundMessage) -> Any:
        """
        Get or create a user based on the platform-specific user identification.
        Returns a User object from your system.
        """
        pass

    @abstractmethod
    def get_or_create_conversation(self, message: InboundMessage) -> Tuple[Any, bool]:
        """
        Get or create a conversation for this chat.
        Returns (conversation, is_new_conversation)
        """
        pass

    @abstractmethod
    def format_message(self, text: str) -> str:
        """
        Format a message for the specific platform (handle markdown, HTML, etc.)
        """
        pass

    @abstractmethod
    def handle_command(
        self, command: str, args: List[str], message: InboundMessage, conversation
    ) -> Tuple[Optional[HttpResponse], Optional[str]]:
        """
        Handle platform-specific commands.
        Returns (http_response, message) where either can be None.
        """
        pass

    @abstractmethod
    def handle_help_command(
        self, args: List[str], message: InboundMessage, conversation
    ) -> Tuple[Optional[HttpResponse], str]:
        """Help command implementation"""
        pass

    @abstractmethod
    def handle_new_command(
        self, args: List[str], message: InboundMessage, conversation
    ) -> Tuple[Optional[HttpResponse], Optional[str]]:
        """
        Start a new conversation with the specified intervention.
        Must be implemented by each platform.
        """
        pass

    @abstractmethod
    def handle_settings_command(
        self, args: List[str], message: InboundMessage, conversation
    ) -> Tuple[Optional[HttpResponse], str]:
        """Settings command implementation"""
        pass

    @abstractmethod
    def send_message(self, chat_id: str, text: str) -> bool:
        """
        Send a message to the platform.
        Returns True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def send_typing_indicator(self, chat_id: str) -> bool:
        """
        Send a typing indicator or equivalent to the platform.
        Returns True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def setup_webhook(self) -> bool:
        """
        Setup the webhook for this client on the platform.
        Returns True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def validate_request(self, request) -> bool:
        """
        Validate that an incoming request is authentic and from the expected platform.
        """
        pass

    @abstractmethod
    def parse_message(self, request) -> InboundMessage:
        """
        Parse the incoming message from the platform's format into a standard InboundMessage.

        Args:
            request: The Django HTTP request object

        Returns:
            InboundMessage object with standardized message data

        Raises:
            ValueError: If the request cannot be parsed as a valid message
        """
        pass

    def handle_web_command(
        self, args: List[str], message: InboundMessage, conversation
    ) -> Tuple[Optional[HttpResponse], str]:
        """
        Generate and send a web link for the conversation.

        TODO: the Webhook and Matrix clients need a base_url or BASE_WEB_URL param on init which is the fully qualified name of the server, so that we can redirect to the full url.
        """
        try:
            if not conversation or conversation.turns.count() == 0:
                return None, "No active conversation found."

            # Get the last turn's UUID
            last_turn = conversation.turns.last()
            if not last_turn:
                return None, "No conversation history found."

            url = reverse("conversation_detail", args=[last_turn.uuid])

            return None, f"Web link to this conversation: {url}"
        except Exception as e:
            logger.error(f"Error generating web link: {e}")
            return None, "Could not generate web link for this conversation."

    def handle_list_command(
        self, args: List[str], message: InboundMessage, conversation
    ) -> Tuple[Optional[HttpResponse], str]:
        """
        List available interventions.
        """
        try:
            available = Intervention.objects.all()
            if not available:
                return None, "No interventions are currently available."

            intervention_list = "\n".join([f"{i.title}: `{i.slug}`" for i in available])
            return None, f"The available interventions are:\n{intervention_list}"
        except Exception as e:
            logger.error(f"Error listing interventions: {e}")
            return None, "Could not retrieve the list of interventions."

    def handle_undo_command(
        self, args: List[str], message: InboundMessage, conversation
    ) -> Tuple[Optional[HttpResponse], str]:
        """
        Undo last turn or a specific turn by UUID.

        # TODO check this logic
        # TODO implement #1 syntax
        """
        try:
            if not conversation or conversation.turns.count() == 0:
                return None, "No active conversation to undo."

            # Determine which turn to branch from
            if args:
                arg = args[0].strip()
                try:
                    # First try to interpret as UUID
                    from_turn = conversation.turns.get(uuid__startswith=arg)
                except Exception:
                    try:
                        # If not UUID, try as number of turns to go back
                        back_n = int(arg)
                        last_turn = conversation.turns.last()
                        turns_list = list(
                            conversation_history(last_turn, to_leaf=False).filter(
                                step__isnull=False
                            )
                        )
                        if back_n <= 0 or back_n > len(turns_list):
                            return (
                                None,
                                f"Invalid number. Please specify a value between 1 and {len(turns_list)}.",
                            )
                        from_turn = turns_list[-back_n]
                    except ValueError:
                        return (
                            None,
                            "Invalid argument. Please specify a valid UUID or number of turns to undo.",
                        )
            else:
                # If no args, undo last turn
                last_turn = conversation.turns.last()
                turns_list = list(
                    conversation_history(last_turn, to_leaf=False).filter(step__isnull=False)
                )
                if not turns_list:
                    return None, "No turns to undo."
                from_turn = turns_list[-1]

            # Create a branch from the selected turn
            new_turn = create_branch(from_turn, reason=BranchReasons.UNDO)

            return None, f"Restarting conversation from:\n\n >{new_turn.text}"

        except Exception as e:
            logger.error(f"Error undoing turn: {e}")
            return None, "Could not undo the conversation. Please try again."

    def _initialise_new_conversation(self, conversation, intervention, user, chat_id):
        """Helper method to initialise a new conversation with an intervention."""

        turn = initialise_new_conversation(conversation, intervention, user)

        # Send the opening message
        self.send_message(chat_id, turn.text)
        return True

    @abstractmethod
    def audio_to_text(self, message):
        """
        Convert audio message to text using transcription.
        This is a placeholder for the actual implementation.
        """
        pass


class WebhookBotClient(MindframeBotClient):
    """
    Base class for webhook-based bot clients like Telegram, Slack, etc.
    """

    bot_name: str = None
    webhook_url: str = None
    bot_secret_token: str = None
    webhook_validation_token: Optional[str] = None
    bot_interface: BotInterface = None

    def __init__(self, bot_interface):
        """Initialize a webhook bot client from BotInterface object"""
        super().__init__()

        self.bot_interface = bot_interface
        self.bot_name = bot_interface.bot_name
        self.bot_secret_token = bot_interface.bot_secret_token
        self.webhook_url = bot_interface.webhook_url()
        self.webhook_validation_token = bot_interface.webhook_validation_token
        # todo: make this a list?
        self.intervention = bot_interface.intervention

    def setup_webhook(self):
        raise NotImplementedError("Not implemented")

    def delete_webhook(self):
        raise NotImplementedError("Not implemented")

    def get_webhook_info(self):
        raise NotImplementedError("Not implemented")

    def validate_request(self, request):
        raise NotImplementedError("Not implemented")

    def parse_message(self, request):
        raise NotImplementedError("Not implemented")

    def get_or_create_conversation(self, message):
        raise NotImplementedError("Not implemented")

    def get_or_create_conversation(self, message):
        raise NotImplementedError("Not implemented")

    def format_message(self, text):
        raise NotImplementedError("Not implemented")

    def send_message(self, chat_id, text):
        raise NotImplementedError("Not implemented")

    def send_typing_indicator(self, chat_id):
        raise NotImplementedError("Not implemented")

    def handle_command(self, message, conversation):
        raise NotImplementedError("Not implemented")

    def process_webhook(self, request):
        raise
