import os

from celery import Celery
from datetime import timedelta


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("practiceprogress")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


app.conf.beat_schedule = {
    'process-practice-records-every-15-minutes': {
        'task': 'record.tasks.process_practice_records_without_feedback',
        'schedule': timedelta(seconds=15)
    },
}