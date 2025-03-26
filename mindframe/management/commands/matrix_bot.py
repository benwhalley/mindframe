import asyncio
import json
import logging
import os
import time
from collections import defaultdict

import nio
from asgiref.sync import sync_to_async
from decouple import Csv, config
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.shortcuts import get_object_or_404

from mindframe.conversation import begin_conversation, listen, respond
from mindframe.models import Conversation, CustomUser, Intervention, Step, Turn
from mindframe.settings import BranchReasons, TurnTypes
from mindframe.tree import conversation_history, create_branch

logger = logging.getLogger(__name__)
User = get_user_model()


MATRIX_HOMESERVER = config("MATRIX_HOMESERVER", "https://matrix.org")
BOT_USERNAME = config("MATRIX_BOT_USERNAME", None)
BOT_PASSWORD = config("MATRIX_BOT_PASSWORD", None)
SESSION_FILE = "matrix_session.json"

# print working directory
print(f"Working directory: {os.getcwd()}")

client = nio.AsyncClient(
    homeserver=MATRIX_HOMESERVER,
    user=BOT_USERNAME,  # Note: it's user_id, not username
    # device_id="MFW",
    store_path="./matrix_crypto_store/",  # Directory to store encryption keys
)


def handle_room_create_event(room: nio.MatrixRoom, event: nio.RoomCreateEvent):
    print(f"Received room create event: {event}")
    print(f"Room: {room}")

    def f_(room):
        conversation, new_conv = Conversation.objects.get_or_create(
            chat_room_id=room.room_id, archived=False
        )

    conversation = sync_to_async(f_)(room)
    print(f"Conversation created: {conversation}")
    return conversation


# def decrypt_message(event):
#     """Decrypt if needed (i.e. if E2EE message)"""
#     if isinstance(event, nio.RoomEncryptionEvent):
#         try:
#             decrypted_event = client.decrypt_event(event)
#             assert isinstance(decrypted_event, nio.RoomMessageText)
#             print(f"DECRYPTED:\n {decrypted_event}")
#             return decrypted_event
#         except:
#             logger.error(f"Failed to decrypt message from {event.sender}")
#             return None


# Replace print statements with this helper function
def log_message(message):
    try:
        Command.stdout.write(Command.stdout.style.SUCCESS(str(message)))
    except AttributeError:
        # Fallback to print if stdout is not available
        print(message)


def handle_help(message):
    return """Commands:
?help - show this message
?new <intervention_slug> - start a new conversation
?settings - show settings
?web - show web page for this conversation
?list - list interventions
?undo - undo last turn
"""


commands_map = {
    "?help": handle_help,
    # "?settings": handle_settings,
    # "/new": handle_new,
    # "/web": handle_web,
    # "/list": handle_list,
    # "/undo": handle_undo,
}


def listen_to_user_input(room, event):
    log_message(f"Received message from {event.sender}: {event.body}")
    conversation, nc_ = Conversation.objects.get_or_create(
        chat_room_id=room.room_id, archived=False
    )
    speaker, ns_ = CustomUser.objects.get_or_create(username=event.sender)
    prev_turn = conversation.turns.all().last()

    if nc_ or not prev_turn:
        logger.info(f"CREATED NEW CONVERSATION: {conversation}")
        nt = Turn.add_root(
            conversation=conversation, speaker=speaker, text=event.body, turn_type=TurnTypes.HUMAN
        )
    else:
        nt = listen(prev_turn, event.body, speaker)
        logger.info(f"FOUND EXISTING CONVERSATION/TURN: {conversation}/{prev_turn}")
        nt = listen(prev_turn, event.body, speaker)

    log_message(f"ADDED HUMAN TURN TO CONVERSATION: {nt}")


async def handle_command(room, event):
    """Handle incoming commands, denoted by leading slash."""
    potential_cmd_ = event.body.split()[0].lower()
    potential_cmd_ = [i for i in commands_map.keys() if potential_cmd_.startswith(i)]
    potential_cmd = potential_cmd_.pop() if potential_cmd_ else None
    logger.info(f"Potential command: {potential_cmd}")
    if potential_cmd:
        response = commands_map[potential_cmd](event.body)
        await send_matrix_message(room.room_id, response)
        return True

    return False


async def respond_to_message(room, event, latest_turn):
    response_turn = sync_to_async(respond)(latest_turn, event.body)
    await client.room_typing(room.room_id, True)
    await send_matrix_message(room.room_id, response_turn.text)
    await client.room_typing(room.room_id, False)


async def message_callback(room: nio.MatrixRoom, event):
    """Handle incoming messages."""

    if event.sender == client.user_id:
        log_message(f"Ignoring own message from {event.sender}")
        # could confirm delivery of Turn
        return  # Ignore bot's own messages

    latest_turn = await sync_to_async(listen_to_user_input)(room, event)

    was_command = await handle_command(room, event)
    print(f"Was command: {was_command}")
    if not was_command:
        respond_to_message(room, event, latest_turn)


# Create content for the response
async def send_matrix_message(room_id, message_body):
    content = {"msgtype": "m.room.message", "body": message_body, "type": "m.text"}
    try:
        # Check if room is encrypted and send accordingly
        if room_id in client.rooms and client.rooms[room_id].encrypted:
            response = await client.room_send(
                room_id=room_id,
                message_type="m.room.message",
                content=content,
                ignore_unverified_devices=True,  # In production, handle this more carefully
            )
        else:
            response = await client.room_send(
                room_id=room_id, message_type="m.room.message", content=content
            )
        print(
            f"Message sent to {room_id}: {message_body[:50]}{'...' if len(message_body) > 50 else ''}"
        )
        return response

    except nio.exceptions.OlmUnverifiedDeviceError as e:
        print(f"Warning: Encryption verification issue in {room_id}: {e}")
        response = await client.room_send(
            room_id=room_id,
            message_type="m.room.message",
            content=content,
            ignore_unverified_devices=True,
        )
        return response

    except Exception as e:
        print(f"Failed to send message to {room_id}: {e}")
        return None


# Replace the previous send_message function with the new one
async def send_message(room_id, message):
    """Send an encrypted message - legacy wrapper for compatibility."""
    return await send_matrix_message(room_id, message)


async def invite_callback(room, event):
    print(f"Received invite to room {room.room_id}")
    await client.join(room.room_id)


async def login():
    if os.path.exists(SESSION_FILE):
        print("Logging in with stored session...")

        with open(SESSION_FILE, "r") as f:
            credentials = json.load(f)

        # Set the credentials on the client
        client.user_id = credentials["user_id"]
        client.device_id = credentials["device_id"]
        client.access_token = credentials["access_token"]
        client.restore_login(client.user_id, client.device_id, client.access_token)

    else:
        print("Logging in with username and password...")
        resp = await client.login(BOT_PASSWORD)

        if isinstance(resp, nio.LoginResponse):
            with open(SESSION_FILE, "w") as f:
                json.dump(
                    {
                        "user_id": client.user_id,
                        "device_id": client.device_id,
                        "access_token": client.access_token,
                    },
                    f,
                )
        else:
            print(f"Failed to log in: {resp}")


# Rate limiting configuration
VERIFICATION_TIMEOUT = 60  # 1 minute between verification attempts
MAX_VERIFICATIONS_PER_HOUR = 10

# Rate limiting state
verification_attempts = defaultdict(list)


def can_verify_user(user_id: str) -> tuple[bool, str]:
    """
    Basic rate limiting check for verification requests.
    Returns (bool, reason_string)
    """
    # Clean up old attempts
    current_time = time.time()
    verification_attempts[user_id] = [
        t
        for t in verification_attempts[user_id]
        if current_time - t < 3600  # Keep attempts from last hour
    ]

    # Check rate limits
    if verification_attempts[user_id]:
        if len(verification_attempts[user_id]) >= MAX_VERIFICATIONS_PER_HOUR:
            return False, "Too many verification attempts in the past hour"

        if current_time - verification_attempts[user_id][-1] < VERIFICATION_TIMEOUT:
            return False, "Please wait a minute before requesting verification again"

    return True, "Verification allowed"


async def verification_request_callback(event):
    """Automatically accept device verification requests."""
    print(f"Received verification request from {event.sender}")

    can_verify, reason = can_verify_user(event.sender)
    if not can_verify:
        print(f"Temporarily blocking verification from {event.sender}: {reason}")
        return

    try:
        # Record the verification attempt
        verification_attempts[event.sender].append(time.time())

        await client.accept_key_verification(event.transaction_id)
        print(f"Accepted verification request {event.transaction_id} from {event.sender}")
    except Exception as e:
        print(f"Error accepting verification request: {e}")


async def verification_start_callback(event):
    print(f"Verification process started: {event.transaction_id}")
    # The next steps depend on the verification method
    # For SAS (emoji) verification:
    if (
        hasattr(event, "short_authentication_string")
        and "emoji" in event.short_authentication_string
    ):
        # Continue with the verification process
        await client.to_device(
            nio.KeyVerificationKey(
                transaction_id=event.transaction_id, key=client.olm.account.identity_keys["ed25519"]
            )
        )


async def verification_key_callback(event):
    print(f"Received verification key: {event.transaction_id}")
    # Process and respond accordingly
    # This is where you'd compute the SAS (emojis)
    # And display them to the user (in logs for a bot)


async def verification_mac_callback(event):
    print(f"Received verification MAC: {event.transaction_id}")
    # Send your own MAC to complete verification
    # await client.to_device(nio.KeyVerificationMac(...))


async def room_key_callback(event):
    print(f"Received a room key for {event.room_id}")
    # The client will automatically handle storing the key


async def to_device_callback(event):
    print(f"Received a to-device event: {event}")
    # Many encryption-related events come as to-device events


def _format_object(obj, indent=0):
    """Helper function to format object attributes recursively."""
    if isinstance(obj, (str, int, float, bool, type(None))):
        return str(obj)

    if isinstance(obj, (list, tuple)):
        items = [f"\n{'  ' * (indent + 1)}- {_format_object(item, indent + 1)}" for item in obj]
        return f"[{''.join(items)}\n{'  ' * indent}]"

    if isinstance(obj, dict):
        items = [
            f"\n{'  ' * (indent + 1)}{key}: {_format_object(value, indent + 1)}"
            for key, value in obj.items()
        ]
        return f"{{{(''.join(items))}\n{'  ' * indent}}}"

    # For other objects, get all attributes that don't start with '_'
    attrs = {}
    for attr in dir(obj):
        if not attr.startswith("_"):  # Skip private/protected attributes
            try:
                value = getattr(obj, attr)
                if not callable(value):  # Skip methods
                    attrs[attr] = value
            except Exception as e:
                attrs[attr] = f"<Error getting attribute: {e}>"

    items = [
        f"\n{'  ' * (indent + 1)}{key}: {_format_object(value, indent + 1)}"
        for key, value in attrs.items()
    ]
    return f"{obj.__class__.__name__}{{{(''.join(items))}\n{'  ' * indent}}}"


async def debug_callback(room, event):
    """Debug callback that prints detailed information about any event."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'='*80}\n{timestamp} - Received event of type: {event.__class__.__name__}")
    print(f"Room: {_format_object(room, indent=1)}")
    print(f"Event: {_format_object(event, indent=1)}")
    print(f"{'='*80}\n")


async def request_missing_keys():
    for room_id in client.rooms:
        print(f"Requesting missing keys for {room_id}")
        await client.room_keys_request(room_id=room_id)


async def send_to_conversation(conversation_id, message):
    await login()
    await request_missing_keys()
    initial_sync_response = await client.sync(since="", full_state=True)
    print(initial_sync_response)

    def f_(conversation_id):
        conversation = Conversation.objects.get(id=conversation_id)
        return conversation

    conversation = await sync_to_async(f_)(conversation_id)
    await send_message(conversation.chat_room_id, message)
    await client.close()


async def main():
    try:
        await login()
        await request_missing_keys()
        print("Performing initial sync...")
        initial_sync_response = await client.sync(timeout=30000, since="", full_state=True)
        print(f"Initial sync complete. Known rooms: {len(client.rooms)}: {client.rooms}")

        # Register debug callback for ALL events
        # client.add_event_callback(debug_callback, nio.Event)

        # Register other specific callbacks
        client.add_event_callback(room_key_callback, nio.RoomKeyEvent)
        client.add_to_device_callback(to_device_callback, nio.ToDeviceEvent)
        client.add_event_callback(verification_request_callback, nio.KeyVerificationEvent)
        client.add_event_callback(verification_start_callback, nio.KeyVerificationStart)
        client.add_event_callback(verification_key_callback, nio.KeyVerificationKey)
        client.add_event_callback(verification_mac_callback, nio.KeyVerificationMac)
        client.add_event_callback(invite_callback, nio.InviteEvent)
        client.add_event_callback(message_callback, nio.RoomMessageText)

        client.add_event_callback(handle_room_create_event, nio.RoomCreateEvent)

        print("Waiting...")
        await client.sync_forever(timeout=5 * 1000)
    finally:
        await client.close()


class Command(BaseCommand):
    """Django management command to start the Matrix bot."""

    help = "Start the Matrix bot to listen for messages."

    def add_arguments(self, parser):
        parser.add_argument("--room-id", type=str, help="Room ID to send a test message to")

        parser.add_argument("--conversation", type=str, help="Conversation ID to send a message to")

        parser.add_argument("--message", type=str, help="Message to send")

    def handle(self, *args, **options):
        if options["conversation"]:
            asyncio.run(send_to_conversation(options["conversation"], options["message"]))
        else:
            asyncio.run(main())


# YY
