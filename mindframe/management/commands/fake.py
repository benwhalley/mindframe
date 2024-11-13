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
from mindframe.silly import silly_user

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Starts a synthetic conversation between two TreatmentSessions or continues an existing one."

    def add_arguments(self, parser):
        parser.add_argument("--i1", type=str, help="Slug of the first intervention.")
        parser.add_argument("--i2", type=str, help="Slug of the second intervention.")
        parser.add_argument(
            "--turns", type=int, required=True, help="Number of turns to complete in total."
        )
        parser.add_argument(
            "--continue", action="store_true", help="Continue an existing SyntheticConversation."
        )
        parser.add_argument(
            "--pk", type=int, help="Primary key of the existing SyntheticConversation to continue."
        )

    def handle(self, *args, **options):
        turns = options["turns"]
        continue_conversation = options["continue"]
        conversation_pk = options.get("pk")

        if continue_conversation:
            # Ensure the primary key is provided when using --continue
            if not conversation_pk:
                raise CommandError(
                    "You must specify the pk of an existing SyntheticConversation to continue with --pk."
                )

            # Fetch the existing conversation and sessions
            conversation = get_object_or_404(SyntheticConversation, pk=conversation_pk)
            session_therapy = conversation.session_one
            session_client = conversation.session_two

            self.stdout.write(
                self.style.SUCCESS(f"Continuing conversation with ID {conversation.pk}.")
            )
        else:
            # Ensure both intervention slugs are provided for a new conversation
            i1 = options["i1"]
            i2 = options["i2"]

            if not i1 or not i2:
                raise CommandError(
                    "You must specify both --i1 and --i2 to start a new conversation."
                )

            # Fetch interventions and create new TreatmentSessions
            therapy_intervention = get_object_or_404(Intervention, slug=i1)
            fake_client_intervention = get_object_or_404(Intervention, slug=i2)

            # Create new client and therapist users
            client_user = silly_user()
            client_user.role = RoleChoices.CLIENT
            client_user.save()

            bot_user = silly_user()
            bot_user.role = RoleChoices.THERAPIST
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

            # Start the conversation with an initial message from the therapist only
            tmnow = timezone.now()
            therapist_initial_text = "Hi, how are you doing today?"
            session_therapy.listen(speaker=bot_user, text=therapist_initial_text, timestamp=tmnow)
            session_client.listen(speaker=bot_user, text=therapist_initial_text, timestamp=tmnow)

        # Continue or add new turns, starting with the client responding, up to the specified turn count
        for i in range(turns):
            if i % 2 == 0:
                # Client's turn
                client_response = session_client.respond()
                session_therapy.listen(speaker=session_client.cycle.client, text=client_response)
            else:
                # Therapist's turn
                therapist_response = session_therapy.respond()
                session_client.listen(speaker=session_therapy.cycle.client, text=therapist_response)

        self.stdout.write(
            self.style.SUCCESS(
                f"Completed {turns} additional turns in conversation ID {conversation.pk}."
            )
        )
