#! bash
# on first run
# cp compose/secrets.en-example compose/secrets.env
# EDIT secrets.env with your own values

(echo "# \! AUTO GENERATED FILE DO NOT EDIT"; docker-compose -f compose/services.yml -f compose/development.yml -p mindframe config) > docker-compose.yml

# build and start the containers
docker-compose build base
docker-compose up -d --build postgres redis
sleep 1
docker-compose up --build web chat worker

# in a new terminal window

# setup database and import demo data
# replace mindframe-postgres-1 with running container name if different
docker exec -it mindframe-postgres-1 create-database.sh mindframe_dbuser mindframe_db mfpassword


docker-compose run web ./manage.py migrate
docker-compose run web ./manage.py loaddata mindframe/fixtures/test.json

# creates a user in mindframe with your current (shell) username
# (change the password and email)
docker-compose run web sh -c "DJANGO_SUPERUSER_PASSWORD=mfpassword ./manage.py createsuperuser --no-input --username=$(whoami) --email=test@example.com"

# open the app in your browser at
open http://127.0.0.1:8080/admin
