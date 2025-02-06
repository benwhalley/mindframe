from celery import shared_task
from django.db import transaction
import logging
from django.apps import apps

logger = logging.getLogger(__name__)

# @shared_task
# def example(id):
#     """
#     Async task to ...
#     """
#     Model = apps.get_model("mindframe", "Model")
#     a = Model.objects.get(id=id)
#     a.do_something()
