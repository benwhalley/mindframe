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

import os
import json
import logging
from django.http import JsonResponse
import traceback
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import get_user_model
from telegram import Update, Bot
from mindframe.models import Conversation, Intervention, RoleChoices, Turn
from mindframe.settings import TurnTextSourceTypes
from mindframe.conversation import listen, respond
import requests
from django.shortcuts import get_object_or_404
import ipaddress
from decouple import config, Csv

logger = logging.getLogger(__name__)
User = get_user_model()

TELEGRAM_WEBHOOK_VALIDATION_TOKEN = config("TELEGRAM_WEBHOOK_VALIDATION_TOKEN")
TELEGRAM_IP_RANGES = [ipaddress.ip_network(ip) for ip in ["149.154.160.0/20", "91.108.4.0/22"]]


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


TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

# https://github.com/python-telegram-bot/python-telegram-bot/issues/4036
# trequest = HTTPXRequest(connection_pool_size=20)
bot = Bot(token=TELEGRAM_BOT_TOKEN)  # , request=trequest)


def send_telegram_message(chat_id, text):
    """Send a Telegram message synchronously using requests."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text, "parse_mode": "MarkdownV2"}

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

    if not is_valid_telegram_request(request):
        logger.warning(f"Rejected request from {request.META.get('REMOTE_ADDR')}")

    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)
    try:
        update = Update.de_json(json.loads(request.body), bot)
        if update.message:
            return process_message(update.message)
    except Exception as e:
        logger.error(f"Telegram webhook error: {e}")
        raise e

    return JsonResponse({"status": "ok"})


def get_conversation(message):
    conversation, new_conv = Conversation.objects.get_or_create(
        telegram_conversation_id=message.chat.id, archived=False
    )
    return conversation, new_conv


def process_message(message):
    """Processes user messages and generates bot responses."""

    try:
        logger.info("Processing message")
        logger.info(message)
        user_data = message.from_user

        # TODO: manage updates to user metadata like name and update our user
        user, created = User.objects.get_or_create(
            username=f"telegram_user_{user_data.id}",
            defaults={
                "first_name": user_data.first_name or "",
                "last_name": user_data.last_name or "",
            },
        )
        # set a default - may be changed below
        interv = Intervention.objects.filter(is_default_intervention=True).order_by("?").first()

        conversation, new_conv = get_conversation(message)

        if message.text.strip().startswith("/help"):
            send_telegram_message(
                message.chat.id,
                "Commands:\n/new <intervention_slug> - start a new conversation\n/help - show this message",
            )
            return JsonResponse({"status": "ok"}, status=200)

        if message.text.strip().startswith("/settings"):
            send_telegram_message(
                message.chat.id,
                "No settings available",
            )
            return JsonResponse({"status": "ok"}, status=200)

        if message.text.strip().startswith("/new"):
            try:
                interv = get_object_or_404(Intervention, slug=message.text.split(" ")[-1].strip())
                logger.info(f"Found the {interv} intervention")
                send_telegram_message(message.chat.id, f"Selected the {interv} intervention")
                conversation.archived = True
                conversation.save()
                send_telegram_message(
                    message.chat.id,
                    "Starting a new conversation (forgetting everything we talked about so far)",
                )
                conversation, new_conv = get_conversation(message)

            except:
                logger.error(str(traceback.format_exc()))
                send_telegram_message(
                    message.chat.id,
                    f"Couldn't find matching intervention, ignoring /new command. (available intervetions are {', '.join(Intervention.objects.all().values_list('slug', flat=True))})",
                )

                return JsonResponse({"status": "ok"}, status=200)

        if new_conv:
            # find a therapist and open the conversation
            send_telegram_message(message.chat.id, f"Creating a new conversation using {interv}")
            therapist, _ = User.objects.get_or_create(
                username="therapist",
                defaults={"role": "therapist", "email": "therapist@example.com"},
            )
            opener = interv.steps.all().first().opening_line
            logger.warning(f"Opening line: {opener}")
            bot_turn = Turn.add_root(
                conversation=conversation,
                speaker=therapist,
                text=interv.steps.all().first().opening_line,
                text_source=TurnTextSourceTypes.OPENING,
                step=interv.steps.all().first(),
            )
            # TODO: work out what to do with user's first turn??
        else:
            # save the user input and respond
            last_turn = conversation.turns.last()
            logger.info(f"Last turn: {last_turn}")

            # create therapist
            if not last_turn:
                last_turn = Turn.add_root(
                    conversation=conversation,
                    speaker=therapist,
                    text=interv.steps.all().first().opening_line,
                    text_source=TurnTextSourceTypes.GENERATED,
                    step=interv.steps.all().first(),
                )

            client_turn = listen(last_turn, speaker=user, text=message.text)
            client_turn.save()

            # respond
            last_turn = conversation.turns.last()
            logger.info(f"RESPONDING TO THIS: {last_turn.text}")
            bot_turn = respond(last_turn)
            bot_turn.save()
            logger.warning(bot_turn.text)

        # Send reply back to Telegram
        logger.info(bot_turn)
        logger.info(bot_turn.text)
        send_telegram_message(message.chat.id, bot_turn.text)

        return JsonResponse({"status": "ok"}, status=200)
    except Exception as e:
        logger.error(str(traceback.format_exc()))
        return JsonResponse({"status": "ok"}, status=200)
