from celery import shared_task
from django.db import transaction
import logging
from django.apps import apps

logger = logging.getLogger(__name__)


# @shared_task
# def example_generate_embedding(example_id):
#     """
#     Async task to generate a text embedding for a given example.
#     """
#     Example = apps.get_model("mindframe", "Example")
#     from mindframe.rag import embed_examples

#     with transaction.atomic():
#         example = Example.objects.filter(id=example_id)
#         embed_examples(example)
#         logger.debug(f"Generated embedding for example {example_id}")
