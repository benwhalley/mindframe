import json

from django.core.management.base import BaseCommand
from django_celery_beat.models import IntervalSchedule, PeriodicTask


class Command(BaseCommand):
    help = "Setup periodic tasks for Celery Beat"

    def handle(self, *args, **kwargs):
        # Create an interval schedule (every minute)
        schedule, created = IntervalSchedule.objects.get_or_create(
            every=1,
            period=IntervalSchedule.MINUTES,
        )

        # Create or update the periodic task
        task, created = PeriodicTask.objects.update_or_create(
            name="execute_nudges_every_minute",
            defaults={
                "interval": schedule,
                "task": "mindframe.tasks.execute_nudges",
                "args": json.dumps([]),
                "kwargs": json.dumps({}),
            },
        )

        if created:
            self.stdout.write(self.style.SUCCESS("Periodic task created"))
        else:
            self.stdout.write(self.style.SUCCESS("Periodic task updated"))
