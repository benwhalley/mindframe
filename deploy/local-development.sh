docker-compose -f compose/local-dev.yml up  -d
docker exec -it postgres /usr/bin/create-database.sh mf mf mf

export DATABASE_URL=postgresql://mf:mf@localhost:5432/mf

docker cp mindframe_db.dump $(docker ps -qf "name=postgres"):/tmp/ && \
docker exec -u postgres -it $(docker ps -qf "name=postgres") \
  pg_restore --clean --if-exists --no-owner --role=postgres -d mf /tmp/mindframe_db.dump

# reset perms so user mf has access
psql -h localhost -p 5432 -U postgres -d mf -f deploy/reset-local-database-perms.sql


# copy secrets to local env so honcho useses them
ln -s ~/.secrets/mf.local.dev.env .env

# start main processes
uv run honcho start -f Procfile.dev

# for other dev commands specify the env file
uv run --env-file=.env ./manage.py makemigrations
