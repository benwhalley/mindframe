import os
from datetime import timedelta

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("mindframe")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# app.conf.beat_schedule = {
#     "something-every-minute": {
#         "task": "mindframe.tasks.embed_examples",
#         "schedule": timedelta(seconds=60),
#     },
# }
