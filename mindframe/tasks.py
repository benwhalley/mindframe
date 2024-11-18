from celery import shared_task
from mindframe.settings import MINDFRAME_AI_MODELS
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


@shared_task
def generate_embedding(example_id, text):
    print("Generating embedding for example")
    from mindframe.models import Example  # avoid circular imports

    embed = MINDFRAME_AI_MODELS.embedding.encode(text)
    print("Done generating embedding")
    with transaction.atomic():
        example = Example.objects.select_for_update().get(id=example_id)
        if example.text == text:
            example.embedding = embed
            example.save()
            logger.info(f"Embedding generated for {example}.")
        else:
            logger.warning(
                f"Text for example changed before embedding completed. Skipping update for {example}."
            )
