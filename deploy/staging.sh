cd ~/dev/mindframe
git push staging main

ssh az1 <<'EOF'
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
docker-compose run web \
    ./manage.py migrate && \
    ./manage.py register_telegram && \
    ./manage.py setup_tasks

docker-compose logs -f web chat worker
EOF
