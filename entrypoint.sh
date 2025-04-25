#!/bin/bash
set -e

APP_TYPE="${DOKKU_APP_TYPE:-django}"

case "$APP_TYPE" in
  "chat")
    echo "Starting chatbot"
    exec python chatbot.py
    ;;
  "django")
    echo "Starting Daphne"
    exec daphne -b 0.0.0.0 -p "$PORT" --verbosity 3 config.asgi:application
    ;;
  *)
    echo "Unknown DOKKU_APP_TYPE: $APP_TYPE"
    exit 1
    ;;
esac
