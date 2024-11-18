import os

from celery import Celery
from datetime import timedelta

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("mindframe")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# app.conf.beat_schedule = {
#     "something-every-15-minutes": {
#         "task": "mindframe.tasks.example",
#         "schedule": timedelta(seconds=15),
#     },
# }
