#! bash
# on first run
# mkdir -p ~/.secrets
# cp compose/mindframe.dev.env-example ~/.secrets/mindframe.dev.env
# EDIT secrets.env with your own values


# BEFORE STARTING

docker network create caddy
docker network create backend


# FOR DEVELOPMENT

(echo "# \! AUTO GENERATED FILE DO NOT EDIT"; \
    CONTAINER_NAME_PREFIX=dev-mindframe \
    WEB_PORT=8080 \
    CHAT_PORT=8081 \
    BASE_IMAGE_NAME="mindframe:dev" \
    docker-compose \
    -f compose/networks.yml \
    -f compose/services.yml \
    -f compose/mindframe.yml \
    -f compose/development.yml \
    -f compose/constraints.yml \
    config) > docker-compose.yml


# BUILD AND START THE PROJECT

# make sure deps are up to date
uv pip compile --output-file requirements.lock pyproject.toml
docker-compose build base


# setup database and default data
docker volume create postgres_data
docker-compose up -d --build postgres redis
docker exec -it postgres create-database.sh mindframe_dbuser mindframe_db mfpassword
docker-compose run web ./manage.py migrate
docker-compose run web ./manage.py loaddata mindframe/fixtures/demo.json
docker-compose run web sh -c \
    "DJANGO_SUPERUSER_PASSWORD=mfpassword \
    ./manage.py createsuperuser --no-input \
    --username=$(whoami) \
    --email=test@example.com"

# register telegram webhooks if using
docker compose run web ./manage.py register_telegram_webhook

# run the site
docker-compose up --build web chat worker

# open http://127.0.0.1:8080





# STAGING
cd ~/dev/mindframe-staging
git reset
(echo "# \! AUTO GENERATED FILE DO NOT EDIT"; \
    CONTAINER_NAME_PREFIX=staging-mindframe \
    WEB_PORT=9080 \
    CHAT_PORT=9081 \
    BASE_IMAGE_NAME="mindframe:staging" \
    docker-compose \
    -f compose/networks.yml \
    -f compose/services.yml \
    -f compose/mindframe.yml \
    -f compose/constraints.yml \
    -f compose/staging.yml \
    config) > docker-compose.yml
docker-compose build base
docker-compose up --build -d web chat worker
docker-compose run web ./manage.py register_telegram_webhook
docker-compose logs -f web chat worker




# LIVE/PRODUCTION
