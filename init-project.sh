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
    WEB_PORT=8080 \
    CHAT_PORT=8081 \
    BASE_IMAGE_NAME="mindframe:dev" \
    docker-compose \
    -f compose/networks.yml \
    -f compose/services.yml \
    -f compose/mindframe.yml \
    -f compose/development.yml \
    -f compose/constraints.yml \
    -p mf \
    config) > docker-compose.yml


# LIVE/PRODUCTION

(echo "# \! AUTO GENERATED FILE DO NOT EDIT"; \
    WEB_PORT=8080 \
    CHAT_PORT=8081 \
    BASE_IMAGE_NAME="mindframe:production" \
    docker-compose \
    -f compose/networks.yml \
    -f compose/services.yml \
    -f compose/mindframe.yml \
    -f compose/live.yml \
    -f compose/constraints.yml \
    -p mflive \
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

# run the site
docker-compose up --build web chat worker
# open http://127.0.0.1:8080





# DEVLOPMENT WORKFLOW
