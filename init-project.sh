#! bash
# on first run
# cp compose/secrets.en-example compose/secrets.env
# EDIT secrets.env with your own values

(echo "# \! AUTO GENERATED FILE DO NOT EDIT"; docker-compose -f compose/services.yml -f compose/app.yml -p mindframe config) > docker-compose.yml

# build and start the containers
docker-compose build base
docker-compose up -d --build postgres redis
sleep 1
docker-compose up -d --build web chat worker


# setup database and import demo data
docker exec -it mindframe-postgres-1 create-database.sh mindframe mindframe mfpassword
docker exec -it mindframe-web-1 ./manage.py migrate
docker exec -it mindframe-web-1 ./manage.py loaddata mindframe/fixtures/demo.json

# list databases
docker exec -it mindframe-postgres-1 psql -U postgres -c "\l"

# creates a user in mindframe with your current (shell) username
# (change the password and email)
docker exec -it mindframe-web-1 sh -c "DJANGO_SUPERUSER_PASSWORD=mfpassword ./manage.py createsuperuser --no-input --username=$(whoami) --email=test@example.com"

# open the app in your browser at
open http://127.0.0.1:8080/admin
