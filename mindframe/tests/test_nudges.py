from datetime import timedelta

import dateparser
from django.test import TransactionTestCase
from django.utils import timezone

from mindframe.models import Conversation, Intervention, Nudge, Step, Turn
from mindframe.silly import silly_user


class NudgeTestCase(TransactionTestCase):  # Instead of TestCase

    def setUp(self):
        """Set up a test Turn instance."""
        c = Conversation.objects.create()
        i = Intervention.objects.create(title="Test Intervention")
        s = Step.objects.create(title="Test Step", intervention=i)
        self.turn = Turn.objects.create(
            lft=1,
            rgt=1,
            tree_id=1,
            depth=1,
            speaker=silly_user(),
            conversation=c,
            timestamp=timezone.now() - timedelta(days=1),
        )

    def test_nudge_not_due_if_starts_in_future(self):
        """Test that a nudge is not due if it starts in the future."""
        n = Nudge.objects.create(
            schedule="daily at 11am, starting in 3 days",
            for_a_period_of="3 months",
            step_to_use=Step.objects.first(),
        )
        self.assertFalse(n.due_for_turn(self.turn))

    def test_nudge_due_if_starts_today(self):
        """Test that a nudge is due if it starts today."""
        n = Nudge.objects.create(
            schedule="daily at 11am, starting today",
            step_to_use=Step.objects.first(),
            for_a_period_of="3 months",
            not_within_n_minutes=0,
        )
        # n.intervention.set([i])
        self.assertTrue(n.due_for_turn(self.turn))

    def test_nudge_expired_if_end_date_passed(self):
        """Test that a nudge is not due if it has expired."""
        n = Nudge.objects.create(
            schedule="daily at 11am", step_to_use=Step.objects.first(), for_a_period_of="1 day"
        )
        end_date = n.end_date_(timezone.now() - timedelta(days=2))
        self.assertFalse(n.due_now(end_date))

    def test_nudge_repeats_correctly(self):
        """Test that a nudge generates the expected number of repeats within a given period."""
        n = Nudge.objects.create(
            schedule="every 6 hours starting now",
            step_to_use=Step.objects.first(),
            for_a_period_of="1 day",
            not_within_n_minuutes=0,
        )
        now = timezone.now()
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)

        datetimes = list(n.scheduled_datetimes(midnight))
        self.assertEqual(len(datetimes), 4)  # Should be 4 nudges in a 24-hour period

    def test_nudge_does_not_repeat_too_soon(self):
        """Test that nudges are not due too soon after the last turn."""
        n = Nudge.objects.create(
            schedule="every 10 minutes", step_to_use=Step.objects.first(), for_a_period_of="1 day"
        )
        self.turn.timestamp = timezone.now() - timedelta(seconds=30)  # Less than NUDGE_WINDOW
        self.assertFalse(n.due_for_turn(self.turn))

    def test_end_date_calculation(self):
        """Test end date calculation from a reference datetime."""
        n = Nudge.objects.create(
            schedule="every day at 8am", step_to_use=Step.objects.first(), for_a_period_of="1 week"
        )
        ref_time = timezone.now()
        end_date = n.end_date_(ref_time)
        expected_end_date = dateparser.parse("after 1 week", settings={"RELATIVE_BASE": ref_time})
        self.assertEqual(end_date.date(), expected_end_date.date())

    def test_invalid_schedule_raises_exception(self):
        """Test that an invalid schedule string raises an exception."""
        n = Nudge(
            schedule="invalid schedule", step_to_use=Step.objects.first(), for_a_period_of="1 week"
        )
        with self.assertRaises(Exception):
            list(n.scheduled_datetimes(timezone.now()))

    def test_nudge_respects_not_within_n_minutes(self):
        """
        Ensure that a nudge isn't due if the last turn happened too recently
        (less than not_within_n_minutes), but is due otherwise.
        """
        # Create a nudge with a frequent schedule (every 10 minutes)
        n = Nudge.objects.create(
            schedule="every 10 minutes",
            step_to_use=Step.objects.first(),
            for_a_period_of="1 day",
            not_within_n_minutes=120,  # Must wait 2 hours after last turn
        )
        # Associate with the relevant Intervention
        n.intervention.set([Intervention.objects.first()])

        # 1) Last turn is only 1 hour ago -> Nudge should NOT be due
        self.turn.timestamp = timezone.now() - timedelta(hours=1)
        self.turn.save()
        self.assertFalse(
            n.due_for_turn(self.turn),
            "Nudge should not be due when last turn is within not_within_n_minutes window.",
        )

        # 2) Last turn is 3 hours ago -> Nudge should be due
        self.turn.timestamp = timezone.now() - timedelta(hours=3)
        self.turn.save()
        self.assertTrue(
            n.due_for_turn(self.turn),
            "Nudge should be due when last turn is outside not_within_n_minutes window.",
        )


# from datetime import timedelta as timedelta
# from django.utils import timezone

# t = Turn.objects.all().last()
# t.timestamp = timezone.now()-timedelta(days=1)
# t.save()

# n = Nudge(
#     schedule="daily 11am, starting in 3 days", for_a_period_of="3 months"
# )
# assert n.due_for_turn(t) == False


# n = Nudge(
#     schedule="daily 11am, starting today days", for_a_period_of="3 months"
# )
# assert n.due_for_turn(t) == True
