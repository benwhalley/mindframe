"""
./manage.py fake --turns=4 demo fake-client-eating
./manage.py fake --turns=2 --continue 41
"""

import logging

from django.core.management.base import BaseCommand, CommandError
from django.shortcuts import get_object_or_404

from mindframe.models import (
    Cycle,
    Intervention,
    RoleChoices,
    SyntheticConversation,
    TreatmentSession,
)
from mindframe.silly import silly_user
from mindframe.synthetic import add_turns

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Starts a synthetic conversation between two TreatmentSessions or continues an existing one."

    def add_arguments(self, parser):
        parser.add_argument(
            "interventions",
            nargs="*",
            type=str,
            help="Slugs of the interventions (two for a new conversation).",
        )
        parser.add_argument(
            "--turns",
            type=int,
            required=True,
            help="Number of turns to complete in total.",
        )
        parser.add_argument(
            "--continue",
            action="store_true",
            help="Continue an existing SyntheticConversation.",
        )

    def handle(self, *args, **options):
        turns = options["turns"]
        continue_conversation = options["continue"]
        interventions = options["interventions"]

        if continue_conversation:
            # Ensure the pk is passed as the first positional argument
            if not interventions:
                raise CommandError(
                    "You must specify the pk of an existing SyntheticConversation to continue."
                )
            conversation_pk = interventions[0]
            # Fetch the existing conversation and sessions
            conversation = get_object_or_404(SyntheticConversation, pk=conversation_pk)
            session_therapy = conversation.session_one
            session_client = conversation.session_two

            self.stdout.write(
                self.style.SUCCESS(f"Continuing conversation with ID {conversation.pk}.")
            )
        else:
            # Ensure both intervention slugs are provided for a new conversation
            if len(interventions) != 2:
                raise CommandError(
                    "You must specify exactly two interventions for a new conversation."
                )

            i1, i2 = interventions

            # Fetch interventions and create new TreatmentSessions
            therapy_intervention = get_object_or_404(Intervention, slug=i1)
            fake_client_intervention = get_object_or_404(Intervention, slug=i2)

            # Create new client and therapist users
            client_user = silly_user()
            client_user.role = RoleChoices.BOT
            client_user.save()

            bot_user = silly_user()
            bot_user.role = RoleChoices.BOT
            bot_user.save()

            self.stdout.write(
                self.style.SUCCESS(f"Created new therapist/client: {bot_user}/{client_user}.")
            )

            # Create cycles and sessions for each intervention
            cycle_therapy = Cycle.objects.create(client=bot_user, intervention=therapy_intervention)
            cycle_client = Cycle.objects.create(
                client=client_user, intervention=fake_client_intervention
            )

            session_therapy = TreatmentSession.objects.create(cycle=cycle_therapy)
            session_client = TreatmentSession.objects.create(cycle=cycle_client)

            # Create new SyntheticConversation
            conversation = SyntheticConversation.objects.create(
                session_one=session_therapy, session_two=session_client
            )

            self.stdout.write(
                self.style.SUCCESS(f"Started new conversation with ID {conversation.pk}.")
            )

        add_turns(conversation, turns)

        self.stdout.write(
            self.style.SUCCESS(
                f"Completed {turns} additional turns in conversation ID {conversation.pk}."
            )
        )
        self.stdout.write(self.style.SUCCESS(conversation.get_absolute_url()))
