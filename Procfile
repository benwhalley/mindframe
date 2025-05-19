web: ./entrypoint.sh
chat: python chatbot.py
worker: celery --app mindframe worker --pool=solo --loglevel=debug
scheduler: celery --app mindframe beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
