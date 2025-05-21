# Telegram Bot docs


## Overview

The Telegram bot integration allows users to interact with MindFrame through Telegram. The bot supports:
- Starting conversations via referal links
- Text-based interactions
- Basic HTML formatting in responses

## Key Components

### TelegramBotClient
Main class handling Telegram interactions:
- Webhook management
- Message parsing
- User management
- Message sending

### Webhook Configuration
The webhook is configured via environment variables:
- `TELEGRAM_BOT_NAME`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_WEBHOOK_URL`
- `TELEGRAM_WEBHOOK_VALIDATION_TOKEN`

### Management Commands
Use `./manage.py telegram` with flags:
- `--register`: Set up webhook
- `--delete`: Remove webhook
- `--info`: Check webhook status


<!--
## Testing

### Simulating Webhook Requests



 -->
