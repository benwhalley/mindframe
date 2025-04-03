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

from mindframe.conversation import initialise_new_conversation, conversation_history
from mindframe.tree import create_branch
from mindframe.models import Intervention
from mindframe.settings import BranchReasons

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


# class TypingIndicatorManager:
#     """
#     Manager for sending typing indicators across different platforms
#     """
#     def __init__(self, client):
#         self.client = client
#         self._typing_threads = {}  # chat_id -> thread
#         self._stop_events = {}     # chat_id -> event

#     def start_typing(self, chat_id: str, interval: float = 3.0) -> None:
#         """
#         Start sending typing indicators for a specific chat.

#         Args:
#             chat_id: The chat ID to send typing indicators to
#             interval: How often to send typing indicators in seconds
#         """
#         # If already typing in this chat, do nothing
#         if chat_id in self._typing_threads and self._typing_threads[chat_id].is_alive():
#             return

#         # Create a new stop event
#         stop_event = threading.Event()
#         self._stop_events[chat_id] = stop_event

#         # Create and start the typing thread
#         thread = threading.Thread(
#             target=self._typing_loop,
#             args=(chat_id, stop_event, interval),
#             daemon=True  # Make thread a daemon so it exits when main thread exits
#         )
#         self._typing_threads[chat_id] = thread
#         thread.start()

#     def stop_typing(self, chat_id: str) -> None:
#         """
#         Stop sending typing indicators for a specific chat.

#         Args:
#             chat_id: The chat ID to stop typing indicators for
#         """
#         if chat_id in self._stop_events:
#             self._stop_events[chat_id].set()

#             # Wait for thread to finish if it's still alive
#             if chat_id in self._typing_threads and self._typing_threads[chat_id].is_alive():
#                 self._typing_threads[chat_id].join(timeout=0.5)

#             # Clean up
#             self._stop_events.pop(chat_id, None)
#             self._typing_threads.pop(chat_id, None)

#     def stop_all_typing(self) -> None:
#         """Stop all typing indicators across all chats"""
#         chat_ids = list(self._stop_events.keys())
#         for chat_id in chat_ids:
#             self.stop_typing(chat_id)

#     def _typing_loop(self, chat_id: str, stop_event: threading.Event, interval: float) -> None:
#         """
#         Background loop that sends typing indicators until stopped.

#         Args:
#             chat_id: The chat ID to send typing indicators to
#             stop_event: Event that will be set when typing should stop
#             interval: How often to send typing indicators in seconds
#         """
#         while not stop_event.is_set():
#             try:
#                 self.client.send_typing_indicator(chat_id)
#             except Exception as e:
#                 logger.error(f"Error sending typing indicator: {e}")

#             # Wait for the interval or until stopped
#             stop_event.wait(timeout=interval)


# class AsyncTypingIndicatorManager:
#     """
#     Manager for sending typing indicators across different platforms with async support
#     """
#     def __init__(self, client):
#         self.client = client
#         self._typing_tasks = {}  # chat_id -> task
#         self._stop_events = {}   # chat_id -> event

#     async def start_typing(self, chat_id: str, interval: float = 3.0) -> None:
#         """
#         Start sending typing indicators for a specific chat.

#         Args:
#             chat_id: The chat ID to send typing indicators to
#             interval: How often to send typing indicators in seconds
#         """
#         # If already typing in this chat, do nothing
#         if chat_id in self._typing_tasks and not self._typing_tasks[chat_id].done():
#             return

#         # Create a new stop event
#         stop_event = asyncio.Event()
#         self._stop_events[chat_id] = stop_event

#         # Create and start the typing task
#         task = asyncio.create_task(self._typing_loop(chat_id, stop_event, interval))
#         self._typing_tasks[chat_id] = task

#     async def stop_typing(self, chat_id: str) -> None:
#         """
#         Stop sending typing indicators for a specific chat.

#         Args:
#             chat_id: The chat ID to stop typing indicators for
#         """
#         if chat_id in self._stop_events:
#             self._stop_events[chat_id].set()

#             # Wait for task to finish if it's still running
#             if chat_id in self._typing_tasks and not self._typing_tasks[chat_id].done():
#                 try:
#                     await asyncio.wait_for(self._typing_tasks[chat_id], timeout=0.5)
#                 except asyncio.TimeoutError:
#                     # If task doesn't finish in time, continue anyway
#                     pass

#             # Clean up
#             self._stop_events.pop(chat_id, None)
#             self._typing_tasks.pop(chat_id, None)

#     async def stop_all_typing(self) -> None:
#         """Stop all typing indicators across all chats"""
#         chat_ids = list(self._stop_events.keys())
#         for chat_id in chat_ids:
#             await self.stop_typing(chat_id)

#     async def _typing_loop(self, chat_id: str, stop_event: asyncio.Event, interval: float) -> None:
#         """
#         Background loop that sends typing indicators until stopped.

#         Args:
#             chat_id: The chat ID to send typing indicators to
#             stop_event: Event that will be set when typing should stop
#             interval: How often to send typing indicators in seconds
#         """
#         while not stop_event.is_set():
#             try:
#                 await self.client.send_typing_indicator(chat_id)
#             except Exception as e:
#                 logger.error(f"Error sending typing indicator: {e}")

#             # Wait for the interval or until stopped
#             try:
#                 await asyncio.wait_for(stop_event.wait(), timeout=interval)
#             except asyncio.TimeoutError:
#                 # This is expected when the timeout expires before the event is set
#                 pass


class MindframeBotClient(ABC):
    """
    Abstract base class for bot clients.
    Base class with common functionality for all clients.
    """

    def __init__(self):
        """Initialize the bot client"""
        pass
        # self.typing_manager = None  # Will be set in subclasses

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
    This handles the synchronous pattern with webhooks.
    """

    bot_name: str = None
    webhook_url: str = None
    bot_secret_token: str = None
    webhook_validation_token: Optional[str] = None
    client_type = ClientType.WEBHOOK

    def __init__(self, bot_name, bot_secret_token, webhook_url=None, webhook_validation_token=None):
        """Initialize webhook bot client"""
        super().__init__()
        self.bot_name = bot_name
        self.bot_secret_token = bot_secret_token
        self.webhook_url = webhook_url
        self.webhook_validation_token = webhook_validation_token

        # self.typing_manager = TypingIndicatorManager(self)


# class ConnectionBotClient(MindframeBotClient):
#     """
#     Base class for connection-based bot clients like Matrix, etc.
#     This handles the asynchronous pattern with persistent connections.
#     """

#     bot_name:Optional[str] = None
#     webhook_url:Optional[str] = None
#     webhook_validation_token:Optional[str] = None
#     bot_secret_token:Optional[str]= None
#     client_type = ClientType.CONNECTION


#     async def setup_typing_manager(self):
#         """Initialize the async typing manager"""
#         self.typing_manager = AsyncTypingIndicatorManager(self)

#     @abstractmethod
#     async def initialize(self) -> bool:
#         """
#         Initialize the client connection.
#         This is where async initialization happens.

#         Returns True if successful, False otherwise.
#         """
#         pass

#     @abstractmethod
#     async def login(self) -> bool:
#         """
#         Log in to the platform.
#         Returns True if successful, False otherwise.
#         """
#         pass

#     @abstractmethod
#     async def register_handlers(self) -> None:
#         """
#         Register message handlers with the platform client.
#         This is where you'd set up callbacks for different event types.
#         """
#         pass

#     @abstractmethod
#     async def start_listening(self) -> None:
#         """
#         Start listening for messages.
#         This typically starts a long-running loop or connection.
#         """
#         pass

#     @abstractmethod
#     async def parse_message(self, event) -> InboundMessage:
#         """
#         Parse a platform event into a standardized InboundMessage.

#         Args:
#             event: The platform-specific event object

#         Returns:
#             InboundMessage object with standardized message data
#         """
#         pass

#     @abstractmethod
#     async def send_message(self, chat_id: str, text: str) -> bool:
#         """
#         Send a message to the platform.
#         Returns True if successful, False otherwise.
#         """
#         pass

#     @abstractmethod
#     async def send_typing_indicator(self, chat_id: str) -> bool:
#         """
#         Send a typing indicator or equivalent to the platform.
#         Returns True if successful, False otherwise.
#         """
#         pass

#     async def start_typing(self, chat_id: str) -> None:
#         """
#         Start sending continuous typing indicators for a chat.
#         """
#         await self.typing_manager.start_typing(chat_id)

#     async def stop_typing(self, chat_id: str) -> None:
#         """
#         Stop sending typing indicators for a chat.
#         """
#         await self.typing_manager.stop_typing(chat_id)
