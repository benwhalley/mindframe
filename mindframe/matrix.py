import asyncio
import json
import logging
import os
import time
from collections import defaultdict

import nio
from decouple import Csv, config
from django.contrib.auth import get_user_model

from mindframe.conversation import begin_conversation, listen, respond
from mindframe.models import Conversation, CustomUser, Intervention, Step, Turn
from mindframe.settings import BranchReasons, TurnTypes
from mindframe.tree import conversation_history, create_branch

logger = logging.getLogger(__name__)
User = get_user_model()


MATRIX_HOMESERVER = "https://matrix.org"
BOT_USERNAME = "@mindframer:matrix.org"
BOT_PASSWORD = "vuwnaz-wagpAt-nymni6"

SESSION_FILE = "matrix_session.json"  # Store session for persistent login

client = nio.AsyncClient(
    homeserver="https://matrix.org",  # Your Matrix homeserver URL
    user=BOT_USERNAME,  # Note: it's user_id, not username
    device_id="MFW",
    store_path="./crypto_store/",  # Directory to store encryption keys
)


def handle_room_create_event(room: nio.MatrixRoom, event: nio.RoomCreateEvent):
    print(f"Received room create event: {event}")
    print(f"Room: {room}")
    conversation, new_conv = Conversation.objects.get_or_create(chat_id=room_id, archived=False)
    print(f"Conversation created: {conversation}")
    return conversation


async def message_callback(room: nio.MatrixRoom, event: nio.RoomMessageText):
    """Handle incoming messages."""
    if event.sender == client.user_id:
        return  # Ignore bot's own messages

    # Decrypt if needed (E2EE message)
    if isinstance(event, nio.RoomEncryptionEvent):
        decrypted_event = await client.decrypt_event(event)
        if isinstance(decrypted_event, nio.RoomMessageText):
            event = decrypted_event
        else:
            print(f"Failed to decrypt message from {event.sender}")
            return

    message_text = event.body
    sender = event.sender

    print(f"Received message from {sender}: {message_text}")

    # Check if bot is mentioned
    if BOT_USERNAME in message_text:
        response_text = f"Hello {sender}, you mentioned me!"
        await send_message(room.room_id, response_text)


async def send_message(room_id, message):
    """Send an encrypted message."""
    content = {"msgtype": "m.text", "body": message}
    await client.room_send(room_id, message_type="m.room.message", content=content)


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
                transaction_id=event.transaction_id,
                key=client.olm.account.identity_keys["ed25519"],
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


async def main():
    try:
        await login()
        print("Performing initial sync...")
        initial_sync_response = await client.sync(timeout=30000)
        print(f"Initial sync complete. Known rooms: {len(client.rooms)}: {client.rooms}")

        # Register debug callback for ALL events
        client.add_event_callback(debug_callback, nio.Event)

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

        for room_id, room in client.rooms.items():
            try:
                await send_message(room_id, "Mindframe is available...")
            except Exception as e:
                print(f"Error sending message to room {room_id}: {e}")

        print("Waiting...")
        await client.sync_forever(timeout=30000)
    finally:
        # Ensure proper cleanup
        await client.close()


asyncio.run(main())

# async def tmp():
#     await login()
#     print("Performing initial sync...")
#     initial_sync_response = await client.sync(timeout=30000)
#     print(f"Initial sync complete. Known rooms: {len(client.rooms)}: {client.rooms}")

#     # Create a copy of room_ids to avoid modifying while iterating
#     room_ids = list(client.rooms.keys())

#     room_ids = list(client.rooms.keys())
#     for room_id in room_ids:
#         print(f"Leaving room: {room_id}")
#         try:
#             response = await client.room_leave(room_id)
#             print(f"Leave response: {response}")
#             # Also forget the room to completely remove it
#             forget_response = await client.room_forget(room_id)
#             print(f"Forget response: {forget_response}")
#         except Exception as e:
#             print(f"Error leaving/forgetting room {room_id}: {e}")

# # Run the function
# asyncio.run(tmp())
