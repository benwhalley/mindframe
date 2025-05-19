# LOCAL

uv pip compile pyproject.toml -o requirements.txt


# REMOTE


dokku postgres:create mf --image "pgvector/pgvector" --image-version "pg17"
echo "CREATE EXTENSION IF NOT EXISTS vector;" | dokku postgres:connect mf

# scp mindframe_db.dump az3:~/mindframe_db.dump
# scp mindframe_db.dump blinky:~/mindframe_db.dump
docker cp mindframe_db.dump $(docker ps -qf "name=dokku.postgres.mf"):/tmp/ && \
docker exec -u postgres -it $(docker ps -qf "name=dokku.postgres.mf") \
  pg_restore --clean --if-exists --no-owner --role=postgres -d mf /tmp/mindframe_db.dump


# for pip caching
mkdir -p /var/lib/dokku/data/storage/pip-cache
chown dokku:dokku /var/lib/dokku/data/storage/pip-cache


# for main app
dokku apps:create mf
dokku ps:scale mf web=1 worker=1 scheduler=1 chat=0
dokku storage:mount mf /var/lib/dokku/data/storage/pip-cache:/app/.cache
dokku postgres:link mf mf
dokku redis:create mf
dokku redis:link mf mf

xargs -a .env dokku config:set mf --no-restart
dokku domains:add mf mf.llemma.net
# deploy first, at least once, before continuing
dokku letsencrypt:set mf email ben.whalley@plymouth.ac.uk
dokku letsencrypt:enable mf




dokku apps:create mfchat
xargs -a .env dokku config:set mfchat --no-restart
dokku config:set mfchat --no-restart MINDFRAME_APP_TYPE="chat"
# chat=0 because dokku needs port 80 to be called `web`; see entrypoint.sh
dokku ps:scale mfchat web=1 worker=0 scheduler=0 chat=0
dokku postgres:link mf mfchat
dokku redis:link mf_redis mfchat
dokku domains:add mfchat mf.bot.llemma.net
# now deploy at least once from local, before
dokku letsencrypt:set mfchat email ben.whalley@plymouth.ac.uk
dokku letsencrypt:enable  mfchat
