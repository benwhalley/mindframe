import logging

from celery import shared_task
from django.apps import apps
from django.db import transaction

from mindframe.conversation import respond
from mindframe.nudge import find_nudges_due
from mindframe.telegram import send_telegram_message

logger = logging.getLogger(__name__)

# @shared_task
# def example(id):
#     """
#     Async task to ...
#     """
#     Model = apps.get_model("mindframe", "Model")
#     a = Model.objects.get(id=id)
#     a.do_something()
