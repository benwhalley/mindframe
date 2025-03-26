from django.test import TransactionTestCase
from django.utils import timezone

from mindframe.conversation import listen, start_conversation, respond
from mindframe.tree import conversation_history, is_interrupted
from mindframe.models import (
    Conversation,
    CustomUser,
    Interruption,
    Intervention,
    Judgement,
    Note,
    Step,
    Turn,
)
from mindframe.settings import RoleChoices, TurnTypes
from mindframe.silly import silly_user


class InterruptionTestCase(TransactionTestCase):
    fixtures = ["mindframe/fixtures/demo.json"]

    def setUp(self):
        """Set up test data for interruption tests."""
        # Create test intervention
        self.intervention = Intervention.objects.get(slug="demo")

        assert (
            self.intervention.interruptions.all().count() > 0
        ), "No interruptions found for demo intervention"

        # Create test users
        self.client_user, _ = CustomUser.objects.get_or_create(
            username="test_client",
            role=RoleChoices.CLIENT,
        )
        self.therapist_user, _ = CustomUser.objects.get_or_create(
            username="test_therapist",
            role=RoleChoices.BOT,
            intervention=self.intervention,
        )

    # def test_interruption_triggered_by_judgement(self):
    #     """Test that an interruption is triggered when a judgement returns True."""
    #     # Create a note that will trigger the interruption
    #     Note.objects.create(
    #         turn=self.initial_turn,
    #         judgement=self.interruption_judgement,
    #         data={"interrupt": True},
    #     )

    #     # System should respond with interruption step
    #     response_turn = self.initial_turn.add_child(
    #         conversation=self.conversation,
    #         speaker=self.therapist_user,
    #         text="...",
    #         step=self.main_step,
    #         turn_type=TurnTypes.BOT,
    #     )
    #     response_turn.save()

    #     # Verify interruption was triggered
    #     self.assertTrue(response_turn.checkpoint)
    #     self.assertEqual(response_turn.interruption, self.interruption)
    #     self.assertEqual(response_turn.step, self.interruption_step)

    # def test_interruption_resolution(self):
    #     """Test that an interruption is resolved when resolution judgement returns True."""
    #     # First trigger the interruption
    #     Note.objects.create(
    #         turn=self.initial_turn,
    #         judgement=self.interruption_judgement,
    #         data={"interrupt": True},
    #     )

    #     # Create checkpoint turn
    #     checkpoint_turn = self.initial_turn.add_child(
    #         conversation=self.conversation,
    #         speaker=self.therapist_user,
    #         text="...",
    #         step=self.main_step,
    #         turn_type=TurnTypes.BOT,
    #     )
    #     checkpoint_turn.checkpoint = True
    #     checkpoint_turn.interruption = self.interruption
    #     checkpoint_turn.save()

    #     # Create a note that will resolve the interruption
    #     Note.objects.create(
    #         turn=checkpoint_turn,
    #         judgement=self.resolution_judgement,
    #         data={"interruption_resolved": True},
    #     )

    #     # System should respond and return to main step
    #     response_turn = checkpoint_turn.add_child(
    #         conversation=self.conversation,
    #         speaker=self.therapist_user,
    #         text="...",
    #         step=self.interruption_step,
    #         turn_type=TurnTypes.BOT,
    #     )
    #     response_turn.save()

    #     # Verify interruption was resolved
    #     self.assertTrue(checkpoint_turn.checkpoint_resolved)
    #     self.assertEqual(response_turn.step, self.main_step)
    #     self.assertEqual(response_turn.resuming_from, checkpoint_turn)

    # def test_interruption_debounce(self):
    #     """Test that interruptions respect the debounce_turns setting."""
    #     # First trigger the interruption
    #     Note.objects.create(
    #         turn=self.initial_turn,
    #         judgement=self.interruption_judgement,
    #         data={"interrupt": True},
    #     )

    #     # Create checkpoint turn
    #     checkpoint_turn = self.initial_turn.add_child(
    #         conversation=self.conversation,
    #         speaker=self.therapist_user,
    #         text="...",
    #         step=self.main_step,
    #         turn_type=TurnTypes.BOT,
    #     )
    #     checkpoint_turn.checkpoint = True
    #     checkpoint_turn.interruption = self.interruption
    #     checkpoint_turn.save()

    #     # Create a turn within debounce period
    #     within_debounce = checkpoint_turn.add_child(
    #         conversation=self.conversation,
    #         speaker=self.therapist_user,
    #         text="...",
    #         step=self.main_step,
    #         turn_type=TurnTypes.BOT,
    #     )
    #     within_debounce.save()

    #     # Create a note that would trigger interruption again
    #     Note.objects.create(
    #         turn=within_debounce,
    #         judgement=self.interruption_judgement,
    #         data={"interrupt": True},
    #     )

    #     # System should respond but not trigger interruption again
    #     response_turn = within_debounce.add_child(
    #         conversation=self.conversation,
    #         speaker=self.therapist_user,
    #         text="...",
    #         step=self.interruption_step,
    #         turn_type=TurnTypes.BOT,
    #     )
    #     response_turn.save()

    #     # Verify interruption was not triggered again
    #     self.assertFalse(response_turn.checkpoint)
    #     self.assertIsNone(response_turn.interruption)

    def test_demo_intervention_interruption_flow(self):
        """Test a complete interruption flow using the demo intervention."""

        # Create conversation
        system_turn = start_conversation(first_speaker=self.therapist_user)

        client_turn = listen(
            system_turn,
            text="Hi, yes I'm here to talk about my eating habits.",
            speaker=self.client_user,
        )

        # System responds (should trigger interruption)
        system_turn = respond(
            client_turn, as_speaker=self.therapist_user, text="checking if we need to interrupt..."
        )

        # Verify risk interruption was not triggered
        self.assertFalse(system_turn.checkpoint)

        client_turn = listen(
            system_turn,
            text="I don't care about my eating. I want to commit suicide.",
            speaker=self.client_user,
        )

        system_turn = respond(
            client_turn,
            as_speaker=self.therapist_user,
            text="we probbaly should talk about this...",
        )

        # Verify risk interruption WAS triggered
        isinter, chpt = is_interrupted(system_turn)
        self.assertTrue(isinter)
        interruption = self.intervention.interruptions.first()
        self.assertEqual(chpt.interruption, interruption)

        # self.assertEqual(system_turn.step, engaging_step)

        # # Client responds during interruption
        # client_turn_2 = system_turn.add_child(
        #     conversation=conversation,
        #     speaker=client,
        #     text="I've been feeling really stressed about my eating lately.",
        #     turn_type=TurnTypes.HUMAN,
        # )

        # # Create resolution judgement
        # resolution_judgement = Judgement.objects.create(
        #     intervention=demo_intervention,
        #     variable_name="resolve_interruption",
        #     prompt_template="[[boolean:interruption_resolved]]",
        # )

        # # Create a note that resolves the interruption
        # Note.objects.create(
        #     turn=client_turn_2,
        #     judgement=resolution_judgement,
        #     data={"interruption_resolved": True},
        # )

        # # System responds (should resolve interruption)
        # system_turn_2 = client_turn_2.add_child(
        #     conversation=conversation,
        #     speaker=therapist,
        #     text="...",
        #     step=engaging_step,
        #     turn_type=TurnTypes.BOT,
        # )
        # system_turn_2.save()

        # # Verify interruption was resolved
        # self.assertTrue(system_turn.checkpoint_resolved)
        # self.assertEqual(system_turn_2.step, opening_step)
        # self.assertEqual(system_turn_2.resuming_from, system_turn)
