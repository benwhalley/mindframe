import logging

from celery import shared_task
from django.apps import apps
from django.db import transaction
from django.db.models import OuterRef, Subquery
from django.utils import timezone

from mindframe.conversation import respond
from mindframe.models import ScheduledNudge
from decouple import config
from mindframe.telegram import TelegramBotClient

from mindframe.tree import conversation_history

logger = logging.getLogger(__name__)

tgmb = TelegramBotClient(
    bot_name="MindframerBot",
    bot_secret_token=config("TELEGRAM_BOT_TOKEN", None),
    webhook_url=config("TELEGRAM_WEBHOOK_URL", None),
    webhook_validation_token=config("TELEGRAM_WEBHOOK_VALIDATION_TOKEN", None),
)


@shared_task
def execute_nudges():

    last_scheduled_nudges_to_execute = ScheduledNudge.objects.due_now()
    logger.info(f"Found {len(last_scheduled_nudges_to_execute)} nudges to execute")

    # due_now only returns a single ScheduledNudge per turn
    for sn in last_scheduled_nudges_to_execute:
        with transaction.atomic():
            # go from the tip because other nudges may have been added to the tree
            turn = conversation_history(sn.turn, to_leaf=True).last()

            newturn = respond(turn, with_intervention_step=sn.nudge.step_to_use)
            newturn.nudge = sn.nudge
            newturn.save()

            if newturn.conversation.chat_room_id:
                logger.info(
                    f"Sending message to Telegram chat: {newturn.conversation.chat_room_id}"
                )
                tgmb.send_message(newturn.conversation.chat_room_id, newturn.text)

            sn.completed = True
            sn.completed_turn = newturn
            sn.save()

            # we need to clean up any other nudges that were scheduled
            outdated_scheduled_nudges = ScheduledNudge.objects.filter(
                turn=sn.turn, nudge=sn.nudge, completed=False, due__lte=sn.due
            )
            logger.info(f"Deleting outdated: {outdated_scheduled_nudges.delete()}")


# execute_nudges()
