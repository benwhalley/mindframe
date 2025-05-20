#!/bin/bash
set -e

APP_TYPE="${MINDFRAME_APP_TYPE:-django}"
WORKERS="${WORKERS:-3}"


case "$APP_TYPE" in
  "chat")
    echo "Starting chatbot"
    exec python chatbot.py
    ;;
  "django")
  exec gunicorn config.asgi:application -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --workers "$WORKERS"
    ;;
  *)
    echo "Unknown MINDFRAME_APP_TYPE: $APP_TYPE"
    exit 1
    ;;
esac
