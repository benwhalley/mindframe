#! bash
# on first run
# mkdir -p ~/.secrets
# cp compose/mindframe.dev.env-example ~/.secrets/mindframe.dev.env
# EDIT secrets.env with your own values


# BUILD DOCKER COMPOSE FILE FOR DEVELOPMENT
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

# make sure python dependencies and container is up to date
uv pip compile --output-file requirements.lock pyproject.toml
# docker-compose build base

# docker-compose up -d --build postgres redis
docker-compose up --build web chat worker



: << 'EOF'
# FIRST RUN, DB SETUP AND CONFIGURATION
docker exec -it postgres create-database.sh mindframe_dbuser mindframe_db mfpassword
docker-compose run web \
    ./manage.py migrate \
    && ./manage.py loaddata mindframe/fixtures/demo.json \
    && ./manage.py setup_tasks
    && ./manage.py register_telegram

docker-compose run web sh -c \
    "DJANGO_SUPERUSER_PASSWORD=mfpassword \
    ./manage.py createsuperuser --no-input \
    --username=admin \
    --email=admin@example.com

# run the site
docker-compose up --build web chat worker

# open http://127.0.0.1:8080

EOF
