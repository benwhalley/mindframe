from celery import shared_task
from django.db import transaction
from mindframe.settings import MINDFRAME_AI_MODELS
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


@shared_task
def generate_embedding(example_id, text):
    """
    Async task to generate a text embedding for a given example.
    """
    from mindframe.models import Example

    embed = MINDFRAME_AI_MODELS.embedding.encode(text)

    with transaction.atomic():
        example = Example.objects.filter(id=example_id)
        # make sure texts match before updating
        if example.first() and example.first().text == text:
            example.update(embedding=embed)
            logger.info(f"Embedding generated for {example}.")
        else:
            logger.warning(
                f"Text for example changed before embedding completed. Skipping update for {example}."
            )
