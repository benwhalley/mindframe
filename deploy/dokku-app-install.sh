# REMOTE

dokku postgres:create mf --image "pgvector/pgvector" --image-version "pg17"
echo "CREATE EXTENSION IF NOT EXISTS vector;" | dokku postgres:connect mf

# scp mindframe_db.dump az3:~/mindframe_db.dump
docker cp mindframe_db.dump $(docker ps -qf "name=dokku.postgres.mf"):/tmp/ && \
docker exec -u postgres -it $(docker ps -qf "name=dokku.postgres.mf") \
  pg_restore --clean --if-exists --no-owner --role=postgres -d mf /tmp/mindframe_db.dump

  pg_restore --clean --if-exists --no-owner --role=postgres -d mf /tmp/mindframe_db.dump


dokku apps:create mf
dokku postgres:link mf mf
dokku ps:scale mf chat=0 web=1 worker=1 scheduler=1
xargs -a .env dokku config:set mf

dokku domains:add mf mf.dokku.llemma.net
dokku letsencrypt:enable  mf


dokku apps:create mfchat
dokku postgres:link mf mfchat
dokku ps:scale mfchat chat=1 web=0 worker=0 scheduler=0


# LOCAL
git remote add az3_mf dokku@az3:mf
git remote add az3_mfchat dokku@az3:mfchat


git checkout dokku && git merge dev && git checkout dev

git push az3_mf dokku:master
git push az3_mfchat dokku:master
