# avowals_fall9t@icloud.com
import asyncio
import os

from nio import (
    AsyncClient,
    AsyncClientConfig,
    LoginResponse,
    MatrixRoom,
    RoomMessageText,
)

MATRIX_HOMESERVER = "https://matrix.org"
BOT_USERNAME = "@mindframer:matrix.org"
BOT_PASSWORD = "vuwnaz-wagpAt-nymni6"
BOT_STORE_DIR = "bot_store"  # Directory to store session data
BOT_STORE = os.path.join(BOT_STORE_DIR, "session.json")

# Global client instance
client = None

# Ensure the store directory exists
os.makedirs(BOT_STORE_DIR, exist_ok=True)


async def message_callback(room: MatrixRoom, event: RoomMessageText) -> None:
    """Handles incoming messages."""
    global client
    if isinstance(event, RoomMessageText):
        decrypted_msg = event.body
        print(f"Received message in {room.display_name}: {decrypted_msg}")

        # Reply to the user
        try:
            await client.room_send(
                room_id=room.room_id,
                message_type="m.room.message",
                content={"msgtype": "m.text", "body": "Hello! I'm an encrypted bot!"},
            )
        except Exception as e:
            print(f"Error sending message: {e}")


async def main():
    """Main bot function."""
    global client

    # Create client config with encryption enabled
    config = AsyncClientConfig(
        store_sync_tokens=True,
        encryption_enabled=True,
    )

    # Create the client with encryption enabled
    client = AsyncClient(
        MATRIX_HOMESERVER,
        BOT_USERNAME,
        store_path=BOT_STORE_DIR,
        config=config,
    )

    # Try to log in
    print("Logging in...")
    response = await client.login(BOT_PASSWORD)

    if not isinstance(response, LoginResponse):
        print(f"Failed to log in: {response}")
        return

    print("Login successful!")

    # Set up event callback
    client.add_event_callback(message_callback, RoomMessageText)

    try:
        # Initial sync to receive encryption keys
        print("Performing initial sync...")
        await client.sync()

        print("Starting event loop...")
        await client.sync_forever(timeout=30000)
    except KeyboardInterrupt:
        print("Bot shutting down...")
    finally:
        await client.close()


# Run the bot
if __name__ == "__main__":
    asyncio.run(main())
