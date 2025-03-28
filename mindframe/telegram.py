"""

# delete
curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/deleteWebhook"

# detup
curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
     -d "url=$TELEGRAM_WEBHOOK_URL" \
     -d "secret_token=$TELEGRAM_WEBHOOK_VALIDATION_TOKEN"

# get webhook status
curl -X GET "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getWebhookInfo"

"""

import ipaddress
import json
import logging
import os
import re
import threading
import time
import traceback

import requests
from decouple import Csv, config
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from telegram import Bot, Update

from mindframe.conversation import begin_conversation, listen, respond
from mindframe.models import Conversation, CustomUser, Intervention, Step, Turn
from mindframe.settings import BranchReasons, TurnTypes
from mindframe.tree import conversation_history, create_branch

logger = logging.getLogger(__name__)
User = get_user_model()

TELEGRAM_WEBHOOK_VALIDATION_TOKEN = config("TELEGRAM_WEBHOOK_VALIDATION_TOKEN", None)
TELEGRAM_IP_RANGES = [ipaddress.ip_network(ip) for ip in ["149.154.160.0/20", "91.108.4.0/22"]]
TELEGRAM_BOT_TOKEN = config("TELEGRAM_BOT_TOKEN", default=None)

bot = TELEGRAM_BOT_TOKEN and Bot(token=TELEGRAM_BOT_TOKEN) or None


if not (TELEGRAM_WEBHOOK_VALIDATION_TOKEN and TELEGRAM_BOT_TOKEN):
    logger.warning("No telegram bot configured")


def send_typing_status_continuous(chat_id, stop_event):
    """Continuously send 'typing' status to Telegram until stop_event is set."""
    while not stop_event.is_set():
        send_typing_status(chat_id)
        time.sleep(5.5)  # Send 'typing' every 4 seconds (before the 5s expiry)


def send_typing_status(chat_id):
    """Send 'typing' status to Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendChatAction"
    data = {"chat_id": chat_id, "action": "typing"}

    try:
        logger.info("Sending 'typing' status.")
        requests.post(url, data=data, timeout=5)
    except requests.RequestException as e:
        logger.warning(f"Failed to send 'typing' status: {e}")


def send_telegram_message(chat_id, text):
    """Send a Telegram message synchronously using requests."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}

    try:
        response = requests.post(
            url, data=data, timeout=10
        )  # Set a timeout to avoid hanging connections
        response.raise_for_status()  # Raise an error for HTTP failures
    except requests.RequestException as e:
        logger.error(f"Failed to send Telegram message: {e}")


@csrf_exempt
def telegram_webhook(request):
    """Handles incoming Telegram messages."""

    print(request)
    if not is_valid_telegram_request(request):
        logger.warning(f"Rejected request from {request.META.get('REMOTE_ADDR')}")

    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)
    try:
        update = Update.de_json(json.loads(request.body), bot)
        if update.message:
            return process_message(update.message, request)
    except Exception as e:
        logger.error(f"Telegram webhook error: {e}")
        raise e

    return JsonResponse({"status": "ok"})


def get_or_create_telegram_user(message) -> CustomUser:
    # TODO: manage updates to user metadata like name and update our user
    user_data = message.from_user
    user, created = User.objects.get_or_create(
        username=f"telegram_user_{user_data.id}",
        defaults={
            "first_name": user_data.first_name or "",
            "last_name": user_data.last_name or "",
        },
    )
    return user


def welcome_message(chat_id):
    send_telegram_message(chat_id, "Hi! This is the mindframe Telegram bot")
    available = Intervention.objects.all().values_list("slug", flat=True)
    send_telegram_message(chat_id, f"")

    send_telegram_message(
        chat_id,
        f"""You can use this system to start a conversation with any of the available therapist interventions, or role-play with a simulated client.

The available intervention names are: {', '.join(available)}

Type /new intervention_name to start a conversation. E.g. /new {available[0]}

(Type /list to see details of all the available interventions)
                          """,
    )


def handle_list(chat_id):
    available = Intervention.objects.all()
    send_telegram_message(chat_id, "The available interventions are:")
    send_telegram_message(chat_id, "\n".join([f"{i.title}: `{i.slug}`" for i in available]))


def handle_help(message, conversation=None, request=None):
    """
    Reply with a summary of available bot commands.
    Returns (JsonResponse, message) so the caller can decide how to proceed.
    """
    logger.info("Handling /help command.")
    send_telegram_message(
        message.chat.id,
        "Commands:\n"
        "/new <intervention_slug> - start a new conversation\n"
        "/help - show this message\n"
        "/settings - show settings",
    )
    return JsonResponse({"status": "ok"}, status=200), None


def handle_web(message, conversation=None, request=None):
    """
    Reply with a link to the web page for this conversation
    """
    try:
        logger.info("Handling /web command.")
        url = request.build_absolute_uri(
            reverse("conversation_detail", args=[conversation.turns.all().last().uuid])
        )
        send_telegram_message(message.chat.id, f"{url}")
        return JsonResponse({"status": "ok"}, status=200), None
    except Exception as e:
        raise e


def handle_settings(message, conversation=None, request=None):
    """
    Reply with any available settings (currently none).
    Returns (JsonResponse, conversation).
    """
    logger.info("Handling /settings command.")
    send_telegram_message(message.chat.id, "No settings available")
    return JsonResponse({"status": "ok"}, status=200), None


def handle_undo(message, conversation, request=None):
    """ """
    parts = message.text.strip().split(" ", 1)

    try:
        from_turn = conversation.turns.get(uuid__startswith=parts[1].strip())
    except Exception:
        logger.info("Couldn't find turn by UUID, trying to find by index")
        back_n = int(parts[1].strip()) if len(parts) > 1 else 1
        last_turn = conversation.turns.last()
        from_turn = list(conversation_history(last_turn, to_leaf=False).filter(step__isnull=False))[
            -back_n
        ]

    new_turn = create_branch(from_turn, reason=BranchReasons.UNDO)
    send_telegram_message(message.chat.id, f"Restarting conversation from:\n\n >{new_turn.text}")
    return JsonResponse({"status": "ok"}, status=200), None


def handle_new(message, conversation, request=None):
    """
    Attempt to start a new conversation with the specified intervention slug.
    If successful, returns (None, new_conversation).
    If fails, returns (JsonResponse, old_conversation).
    """
    logger.info("Handling /new command.")
    try:
        parts = message.text.strip().split(" ", 1)
        slug = parts[1].strip() if len(parts) > 1 else None
        if not slug:
            raise ValueError("No intervention slug provided")

        intervention = get_object_or_404(Intervention, slug=slug)

        # Archive old conversation and notify user
        conversation.archived = True
        conversation.save(update_fields=["archived"])  # Ensures DB commit
        send_telegram_message(
            message.chat.id,
            "Starting a new conversation (forgetting everything we talked about so far).",
        )
        logger.info(f"conv id {conversation.uuid}")
        del conversation

        conversation, is_new = get_or_create_conversation(message)
        begin_conversation(intervention, conversation, message.chat.id)

        return JsonResponse({"status": "ok"}, status=200), None

    except Exception as e:
        logger.error(traceback.format_exc())
        available = ", ".join(Intervention.objects.all().values_list("slug", flat=True))
        send_telegram_message(
            message.chat.id,
            f"Couldn't find matching intervention, ignoring /new command.\n"
            f"(Available interventions: {available})",
        )
        # Return a JsonResponse and the old conversation
        return None, None


def start_new_telegram_conversation(intervention, conversation, chat_id):
    bot_turn, messages_to_send = start_new_conversation(intervention, conversation, chat_id)
    send_telegram_message(chat_id, messages_to_send)
    return bot_turn


def continue_conversation(message, telegram_user, conversation, intervention):
    """
    Save the user's turn and generate a bot response in the ongoing conversation.
    """
    last_turn = conversation.turns.last()

    # If no prior turns exist, create a default opening
    if not last_turn:
        therapist, _ = User.objects.get_or_create(
            username="therapist",
            defaults={"role": "therapist", "email": "therapist@example.com"},
        )
        first_step = intervention.steps.first()
        opener_text = first_step.opening_line if first_step else "Hello! (No opening line set.)"
        last_turn = Turn.add_root(
            conversation=conversation,
            speaker=therapist,
            text=opener_text,
            turn_type=TurnTypes.OPENING,
            step=first_step,
        )

    # Record the user's turn
    client_turn = listen(last_turn, speaker=telegram_user, text=message.text)
    client_turn.save()

    # Generate bot response
    last_turn = conversation.turns.last()
    logger.info(f"Responding to this: {last_turn.text}")

    # continuously send 'typing' status messages while generating response
    # using a thread (because typing status expires after 5 seconds)
    stop_event = threading.Event()
    typing_thread = threading.Thread(
        target=send_typing_status_continuous, args=(message.chat.id, stop_event)
    )
    typing_thread.start()
    try:
        bot_turn = respond(last_turn)  # This could take time
    finally:
        stop_event.set()  # Stop sending 'typing' once `respond` completes
        typing_thread.join()

    bot_turn.save()
    logger.info(f"Bot response: {bot_turn.text}")

    # Send reply
    send_telegram_message(message.chat.id, f"{bot_turn.text}      [{bot_turn.uuid[:3]}]")


def process_message(message, request=None):
    """
    Main entry point for handling incoming messages.
    1) Identify the user and conversation
    2) Use a dictionary-based command dispatch where each handler returns:
        (JsonResponse or None, conversation)
    3) If the handler returned a JsonResponse, we return it immediately.
    4) Otherwise, we continue or start a conversation as appropriate.
    """
    logger.info("Processing message.")
    logger.info(message)

    try:
        telegram_user = get_or_create_telegram_user(message)
        text_stripped = (message.text or "").strip()

        # TODO: handle audio and video here
        if not text_stripped:
            send_telegram_message(message.chat.id, "Sorry, I only understand text at the moment...")
            return JsonResponse({"status": "ok"}, status=200)

        # Build a command map: each handler returns (JsonResponse or None, conversation)
        commands_map = {
            "/help": handle_help,
            "/settings": handle_settings,
            "/new": handle_new,
            "/web": handle_web,
            "/list": handle_list,
            "/undo": handle_undo,
        }

        # Extract potential command
        potential_cmd = text_stripped.split()[0].lower() if text_stripped.startswith("/") else None

        # Fetch default intervention
        default_intervention = (
            Intervention.objects.filter(is_default_intervention=True).order_by("?").first()
        )

        # Get conversation
        conversation, is_new_conv = get_or_create_conversation(message)

        # Dispatch command if recognised
        if potential_cmd in commands_map:
            response, message = commands_map[potential_cmd](message, conversation, request)
            if response is not None:
                # If the command returned a response, return it now
                return response
            if message is not None:
                send_telegram_message(message.chat.id, message)

        # If conversation is brand-new or newly replaced, start anew
        if is_new_conv or conversation.turns.count() == 0:
            welcome_message(message.chat.id)
        else:
            # Continue existing conversation
            continue_conversation(message, telegram_user, conversation, default_intervention)

        return JsonResponse({"status": "ok"}, status=200)

    except Exception:
        logger.error(traceback.format_exc())
        return JsonResponse({"status": "error"}, status=200)


def is_valid_telegram_request(request):
    """Check if the request originates from a valid Telegram IP."""

    client_ip = request.META.get("HTTP_X_FORWARDED_FOR")
    ip = ipaddress.ip_address(client_ip)
    valid_ip = any(ip in net for net in TELEGRAM_IP_RANGES)
    valid_ip = True

    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != TELEGRAM_WEBHOOK_VALIDATION_TOKEN:
        valid_header = False
    else:
        valid_header = True
    logger.info(f"Valid IP: {valid_ip}, valid header: {valid_header}")
    return valid_ip and valid_header


def get_or_create_conversation(message):
    logger.info(f"Getting conversation for chat ID {message.chat.id}")
    conversation, new_conv = Conversation.objects.get_or_create(
        chat_room_id=message.chat.id, archived=False
    )
    return conversation, new_conv
