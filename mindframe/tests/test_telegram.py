import json
import pickle

import requests
from box import Box
from decouple import config

from mindframe.models import Conversation
from mindframe.telegram import TelegramBotClient
from llmtools.llm_calling import transcribe_audio
import logging

logger = logging.getLogger(__name__)


tgmb = TelegramBotClient(
    bot_name="MindframerBot",
    bot_secret_token=config("TELEGRAM_BOT_TOKEN", None),
    webhook_url=config("TELEGRAM_WEBHOOK_URL", None),
    webhook_validation_token=config("TELEGRAM_WEBHOOK_VALIDATION_TOKEN", None),
)

tgmb

# tgmb.setup_webhook()
# tgmb.webhook_url

# PROCESS TEXT MESSAGE

# request = Box(pickle.load(open("telegram_textrequest.pickle", "rb")))
# tgmb.validate_request(request)

# inbound = tgmb.parse_message(request)
# speaker = tgmb.get_or_create_user(inbound)
# speaker.username == "telegram_user_6515550712"
# conversation, new_ = tgmb.get_or_create_conversation(inbound)
# print(conversation)

# tgmb.send_typing_indicator(conversation.chat_room_id)
# tgmb.send_message(conversation.chat_room_id, "Hello, this is a test message")


# def amend_request_message_text_(request, newtext):
#     bb = json.loads(request.body)
#     bb['message']['text'] = newtext
#     request.body = json.dumps(bb)
#     return request


# tgmb.process_webhook(amend_request_message_text_(request, "/help")) # TODO NOT WORKING

# # start a new conversation and check it's created
# a = Conversation.objects.count()
# tgmb.process_webhook(amend_request_message_text_(request, "/new demo"))
# b = Conversation.objects.count()  # TODO: not created properly at moment
# conversation, new_ = tgmb.get_or_create_conversation(inbound)
# a < b, conversation


# # respond as a client, check the conversation has 2 extra turns
# a = conversation.turns.all().count()
# tgmb.process_webhook(amend_request_message_text_(request, "yeah ok"))
# b = conversation.turns.all().count()
# a < b


# tgmb.process_webhook(amend_request_message_text_(request, "/list"))
# tgmb.process_webhook(amend_request_message_text_(request, "/web"))

# tgmb.process_webhook(amend_request_message_text_(request, "/blah"))


# EXAMPLE OF DOWNLOADING AUDIO

request = Box(pickle.load(open("telegram_audiorequest.pickle", "rb")))
request
am = tgmb.parse_message(request)
file_id = am.media[0].file_id
file_info_url = f"https://api.telegram.org/bot{tgmb.bot_secret_token}/getFile?file_id={file_id}"

response = requests.get(file_info_url)
file_path = response.json()["result"]["file_path"]
file_url = f"https://api.telegram.org/file/bot{tgmb.bot_secret_token}/{file_path}"

transcribe_audio(file_url, "en")


# EXAMPLE OF DOWNLOADING VIDEO

request = Box(pickle.load(open("telegram_videorequest.pickle", "rb")))
request
vm = tgmb.parse_message(request)
file_id = vm.media[0].file_id
file_info_url = f"https://api.telegram.org/bot{tgmb.bot_secret_token}/getFile?file_id={file_id}"
response = requests.get(file_info_url)
file_path = response.json()["result"]["file_path"]
file_url = f"https://api.telegram.org/file/bot{tgmb.bot_secret_token}/{file_path}"

transcribe_audio(file_url, "en")
