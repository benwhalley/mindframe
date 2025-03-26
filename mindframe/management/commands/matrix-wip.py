"""
TODO:

- handle reactions and log them against turns


Matrix API does not support direct timestamp-based sync.
Instead, you must fetch the sync token closest to the desired timestamp.
This means:
Fetch events before the given datetime.
Use the last sync token before the datetime.



"""

import asyncio
import json
import logging
import os
import time
from typing import Optional

import nio
from decouple import config
from django.core.management.base import BaseCommand
from nio import AsyncClient

from mindframe.models import Turn

logger = logging.getLogger(__name__)


# Matrix bot configuration
MATRIX_HOMESERVER = config("MATRIX_HOMESERVER", "https://matrix.org")
BOT_USERNAME = config("MATRIX_BOT_USERNAME", "@mindframer:matrix.org")
BOT_PASSWORD = config("MATRIX_BOT_PASSWORD", "vuwnaz-wagpAt-nymni6")
SESSION_FILE = "session.json"
STORE_PATH = "matrix_store/"  # Directory to store encryption keys and other data


def ensure_store_path():
    """Ensure the store directory exists."""
    if not os.path.exists(STORE_PATH):
        os.makedirs(STORE_PATH)


def _format_object(obj, indent=0):
    """Helper function to format object attributes recursively for printing."""
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


class MatrixBot:
    """A Matrix bot that listens for messages and responds."""

    def __init__(self):
        # Ensure store directory exists
        ensure_store_path()

        # Configure the client with encryption support
        config = nio.AsyncClientConfig(
            encryption_enabled=True,
            store_sync_tokens=True,
        )

        self.client = AsyncClient(
            MATRIX_HOMESERVER,
            BOT_USERNAME,
            device_id="MFW",
            store_path=STORE_PATH,  # Use the constant defined at module level
            config=config,
        )
        self.is_ready = False

    async def get_last_update(self):
        """Get the timestamp of the last Turn asynchronously."""
        last_turn = await sync_to_async(
            lambda: Turn.objects.filter(conversation__chat_room_id__isnull=False).last()
        )()
        return last_turn.timestamp if last_turn else None

    async def run(self):
        """Start the Matrix bot."""
        try:
            await self.login()
            await self.register_event_callbacks()
            self.is_ready = True
            logger.info("Matrix bot is running...")

            # Start with initial sync to get the current state
            logger.info("Performing initial sync...")
            initial_sync_response = await self.client.sync(
                timeout=30000, full_state=True  # Get full state on initial sync
            )
            logger.info(f"Initial sync complete. Known rooms: {len(self.client.rooms)}")

            # Request keys for all joined rooms after initial sync
            for room_id in self.client.rooms:
                try:
                    await self.client.request_room_keys(room_id)
                except Exception as e:
                    logger.warning(f"Failed to request initial room keys for {room_id}: {e}")

            # Start the sync loop
            sync_token = initial_sync_response.next_batch
            while True:
                sync_response = await self.client.sync(timeout=30000, since=sync_token)
                sync_token = sync_response.next_batch
                await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Error running bot: {e}")
            raise

    async def login(self):
        """Login to Matrix, using stored session if available."""
        try:
            if os.path.exists(SESSION_FILE):
                with open(SESSION_FILE, "r") as f:
                    credentials = json.load(f)

                self.client.user_id = credentials["user_id"]
                self.client.device_id = credentials["device_id"]
                self.client.access_token = credentials["access_token"]
                self.client.restore_login(
                    self.client.user_id, self.client.device_id, self.client.access_token
                )
                # Load encryption keys after restoring session
                try:
                    await self.client.load_store()
                except Exception as e:
                    logger.error(f"Error loading store: {e}")
                # Initialize encryption after loading store
                try:
                    await self.client.init_encryption()
                except Exception as e:
                    logger.error(f"Error initializing encryption: {e}")
                logger.info("Restored previous session and loaded encryption keys")
                logger.info(f"Credentials: {credentials}")
            else:
                logger.info("Logging in with password...")
                resp = await self.client.login(BOT_PASSWORD)
                if isinstance(resp, nio.LoginResponse):
                    with open(SESSION_FILE, "w") as f:
                        json.dump(
                            {
                                "user_id": self.client.user_id,
                                "device_id": self.client.device_id,
                                "access_token": self.client.access_token,
                            },
                            f,
                        )
                    # Initialize encryption store and encryption after fresh login
                    try:
                        await self.client.load_store()
                    except Exception as e:
                        logger.error(f"Error loading store: {e}")

                    await self.client.init_encryption()
                    logger.info("Login successful and encryption initialized")
                else:
                    raise Exception(f"Login failed: {resp}")
        except Exception as e:
            logger.error(f"Error during login: {e}")
            raise

    async def ensure_room_joined(self, room_id: str) -> bool:
        """Ensure the bot is joined to the specified room."""
        try:
            # Check if we're already in the room
            rooms = await self.client.joined_rooms()
            if room_id in rooms.rooms:
                room = self.client.rooms[room_id]
                if room.encrypted:
                    # For encrypted rooms, ensure we have keys
                    await self.share_keys_with_room(room_id)
                return True

            # Try to join the room
            response = await self.client.join(room_id)
            if isinstance(response, nio.JoinResponse):
                logger.info(f"Successfully joined room {room_id}")
                # After joining, share keys if room is encrypted
                room = self.client.rooms[room_id]
                if room.encrypted:
                    await self.share_keys_with_room(room_id)
                return True
            else:
                logger.error(f"Failed to join room {room_id}: {response}")
                return False
        except Exception as e:
            logger.error(f"Error joining room {room_id}: {e}")
            return False

    async def send_message(self, room_id: str, message: str) -> bool:
        """Send a message to a specific room."""
        try:
            # Ensure we're in the room before sending
            if not await self.ensure_room_joined(room_id):
                raise Exception(f"Could not join room {room_id}")

            content = {"msgtype": "m.text", "body": message}
            response = await self.client.room_send(
                room_id, "m.room.message", content, ignore_unverified_devices=True
            )

            if isinstance(response, nio.RoomSendResponse):
                logger.info(f"Message sent successfully to {room_id}")
                return True
            else:
                logger.error(f"Failed to send message: {response}")
                return False
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False

    async def debug_callback(self, room, event):
        """Debug callback that prints detailed information about any event."""

        pass
        # timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        # print(f"\n{'='*80}\n{timestamp} - Received event of type: {event.__class__.__name__}")
        # print(f"Room: {_format_object(room, indent=1)}")
        # print(f"Event: {_format_object(event, indent=1)}")
        # print(f"{'='*80}\n")

    async def register_event_callbacks(self):
        """Register event handlers."""
        # Add handlers for encryption-related events
        self.client.add_event_callback(self.room_key_callback, nio.RoomKeyEvent)
        self.client.add_to_device_callback(self.to_device_callback, nio.ToDeviceEvent)
        self.client.add_event_callback(self.verification_request_callback, nio.KeyVerificationEvent)
        self.client.add_event_callback(self.verification_start_callback, nio.KeyVerificationStart)
        self.client.add_event_callback(self.verification_key_callback, nio.KeyVerificationKey)
        self.client.add_event_callback(self.verification_mac_callback, nio.KeyVerificationMac)

        # Add standard message handlers
        self.client.add_event_callback(self.message_callback, nio.RoomMessageText)
        self.client.add_event_callback(self.invite_callback, nio.InviteEvent)
        self.client.add_event_callback(self.debug_callback, nio.Event)

    async def room_key_callback(self, event):
        """Handle room key events."""
        logger.info(f"Received a room key for {event.room_id}")

    async def to_device_callback(self, event):
        """Handle to-device events."""
        logger.info(f"Received a to-device event: {event}")
        try:
            if isinstance(event, nio.OlmEvent):
                # Try to decrypt the Olm event
                try:
                    decrypted = await self.client.decrypt_event(event)
                    logger.info(f"Successfully decrypted Olm event: {decrypted}")
                except Exception as e:
                    logger.warning(f"Could not decrypt Olm event: {e}")

                # If we got a room key event, immediately try to request keys
                if isinstance(decrypted, nio.RoomKeyEvent):
                    await self.client.request_room_keys(decrypted.room_id)
        except Exception as e:
            logger.error(f"Error handling to-device event: {e}")

    async def verification_request_callback(self, event):
        """Handle verification requests."""
        logger.info(f"Received verification request from {event.sender}")
        try:
            await self.client.accept_key_verification(event.transaction_id)
            logger.info(f"Accepted verification request {event.transaction_id} from {event.sender}")
        except Exception as e:
            logger.error(f"Error accepting verification request: {e}")

    async def verification_start_callback(self, event):
        """Handle verification start events."""
        logger.info(f"Verification process started: {event.transaction_id}")
        if (
            hasattr(event, "short_authentication_string")
            and "emoji" in event.short_authentication_string
        ):
            await self.client.to_device(
                nio.KeyVerificationKey(
                    transaction_id=event.transaction_id,
                    key=self.client.olm.account.identity_keys["ed25519"],
                )
            )

    async def verification_key_callback(self, event):
        """Handle verification key events."""
        logger.info(f"Received verification key: {event.transaction_id}")

    async def verification_mac_callback(self, event):
        """Handle verification MAC events."""
        logger.info(f"Received verification MAC: {event.transaction_id}")

    async def message_callback(self, room, event: nio.RoomMessageText):
        """Handle incoming messages."""
        if event.sender == self.client.user_id:
            return  # Ignore own messages

        # Decrypt if needed (E2EE message)
        if isinstance(event, nio.MegolmEvent):
            try:
                # Request keys if we don't have them
                if not self.client.olm.has_session(room.room_id, event.session_id):
                    logger.info(
                        f"Requesting keys for session {event.session_id} in room {room.room_id}"
                    )
                    await self.client.request_room_keys(room.room_id)

                decrypted_event = await self.client.decrypt_event(event)
                if isinstance(decrypted_event, nio.RoomMessageText):
                    event = decrypted_event
                    logger.info("Successfully decrypted message")
                else:
                    logger.warning(
                        f"Decrypted event is not a text message: {type(decrypted_event)}"
                    )
                    return
            except Exception as e:
                logger.error(f"Failed to decrypt message: {e}")
                return

        message_text = event.body
        sender = event.sender

        logger.info(f"Received message from {sender}: {message_text}")
        await self.send_message(room.room_id, f"Echo: {message_text}")

    async def invite_callback(self, room, event):
        """Handle room invites."""
        logger.info(f"Received invite to room {room.room_id}")
        try:
            # Join the room
            response = await self.client.join(room.room_id)
            if isinstance(response, nio.JoinResponse):
                logger.info(f"Successfully joined room {room.room_id}")

                # After joining, mark the room as encrypted if needed
                if room.encrypted:
                    logger.info(f"Room {room.room_id} is encrypted, setting up encryption")
                    try:
                        # Share keys with all devices in the room
                        await self.share_keys_with_room(room.room_id)
                    except Exception as e:
                        logger.error(f"Error sharing keys with room: {e}")
            else:
                logger.error(f"Failed to join room: {response}")
        except Exception as e:
            logger.error(f"Error handling invite: {e}")

    async def share_keys_with_room(self, room_id: str):
        """Share encryption keys with all devices in a room."""
        try:
            # Get all users in the room
            response = await self.client.joined_members(room_id)
            if not isinstance(response, nio.JoinedMembersResponse):
                logger.error(f"Failed to get room members: {response}")
                return

            # For each user, get their devices and share keys
            for user_id in response.members:
                try:
                    # Get user's devices
                    devices = await self.client.query_keys({user_id: []})
                    if not isinstance(devices, nio.QueryKeysResponse):
                        logger.error(f"Failed to query keys for {user_id}: {devices}")
                        continue

                    # Trust all devices for now (in production, you might want to be more selective)
                    for device_id, device in devices.device_keys.get(user_id, {}).items():
                        try:
                            await self.client.verify_device(device)
                            logger.info(f"Verified device {device_id} for user {user_id}")
                        except Exception as e:
                            logger.warning(
                                f"Could not verify device {device_id} for {user_id}: {e}"
                            )

                except Exception as e:
                    logger.error(f"Error processing devices for user {user_id}: {e}")

            # Request room keys again after sharing
            await self.client.request_room_keys(room_id)

        except Exception as e:
            logger.error(f"Error sharing keys with room: {e}")


class Command(BaseCommand):
    """Django management command to start the Matrix bot."""

    help = "Start the Matrix bot to listen for messages."

    def add_arguments(self, parser):
        parser.add_argument("--room-id", type=str, help="Room ID to send a test message to")
        parser.add_argument("--message", type=str, help="Message to send")

    def handle(self, *args, **options):
        bot = MatrixBot()

        if options.get("room_id") and options.get("message"):

            async def send_test_message():
                try:
                    await bot.login()
                    success = await bot.send_message(options["room_id"], options["message"])
                    if success:
                        self.stdout.write(self.style.SUCCESS("Message sent successfully"))
                    else:
                        self.stdout.write(self.style.ERROR("Failed to send message"))
                finally:
                    await bot.client.close()

            asyncio.run(send_test_message())
        else:

            async def run_bot():
                try:
                    await bot.run()
                finally:
                    await bot.client.close()

            asyncio.run(run_bot())
