web: daphne -b 0.0.0.0 -p $PORT --verbosity 3 config.asgi:application
chat: python chatbot.py
worker: celery --app mindframe worker --pool=solo --loglevel=debug
scheduler: celery --app mindframe beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
