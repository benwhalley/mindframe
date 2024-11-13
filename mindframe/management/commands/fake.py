from django.core.management.base import BaseCommand, CommandError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from mindframe.models import (
    Intervention,
    CustomUser,
    TreatmentSession,
    SyntheticConversation,
    Turn,
    Cycle,
    RoleChoices,
)

import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Starts a synthetic conversation between two TreatmentSessions or continues an existing one."

    def add_arguments(self, parser):
        parser.add_argument("--i1", type=str, required=True, help="Slug of the first intervention.")
        parser.add_argument(
            "--i2", type=str, required=True, help="Slug of the second intervention."
        )
        parser.add_argument(
            "--turns", type=int, required=True, help="Number of turns to complete in total."
        )
        parser.add_argument(
            "--continue",
            action="store_true",
            help="Continue an existing SyntheticConversation.",
        )
        parser.add_argument(
            "--pk",
            type=int,
            help="Primary key of the existing SyntheticConversation to continue.",
        )

    def handle(self, *args, **options):
        i1 = options["i1"]
        i2 = options["i2"]
        turns = options["turns"]

        # Fetch interventions and create new TreatmentSessions
        therapy_intervention = get_object_or_404(Intervention, slug=i1)
        fake_client_intervention = get_object_or_404(Intervention, slug=i2)

        client_user = CustomUser.objects.filter(role=RoleChoices.CLIENT).first()
        bot_user = CustomUser.objects.filter(role=RoleChoices.THERAPIST).first()

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

        # Start the conversation with an initial message from the therapist only
        tmnow = timezone.now()
        therapist_initial_text = "Hi, how are you doing today?"
        session_therapy.listen(speaker=bot_user, text=therapist_initial_text, timestamp=tmnow)
        session_client.listen(speaker=bot_user, text=therapist_initial_text, timestamp=tmnow)

        # Alternate turns, starting with the client responding, up to the specified turn count
        for i in range(turns):  # starts from 0
            if i % 2 == 0:
                # Client's turn
                client_response = session_client.respond()
                session_therapy.listen(speaker=client_user, text=client_response)
            else:
                # Therapist's turn
                therapist_response = session_therapy.respond()
                session_client.listen(speaker=bot_user, text=therapist_response)

        self.stdout.write(
            self.style.SUCCESS(f"Completed {turns} turns in conversation ID {conversation.pk}.")
        )
