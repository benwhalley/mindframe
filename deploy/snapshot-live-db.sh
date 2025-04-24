
ssh az2 <<'EOF'
docker exec -it postgres pg_dump -O -f mindframe_db.dump -F c -d mindframe_db -h 127.0.0.1 -p 5432 -U postgres
docker cp postgres:/mindframe_db.dump  ~/mindframe_db.dump
ls -la ~/
EOF


# # # local
scp az2:~/mindframe_db.dump mindframe_db.dump
docker exec -it postgres dropdb -U postgres mindframe_db
docker exec -it postgres create-database.sh mindframe_dbuser mindframe_db mfpassword
docker cp mindframe_db.dump postgres:/mindframe_db.dump
docker exec -it postgres pg_restore -v -U postgres  --no-owner  -d mindframe_db /mindframe_db.dump
docker cp deploy/reset_perms.sql  postgres:/reset_perms.sql
docker exec -it postgres psql -U postgres -d mindframe_db -f /reset_perms.sql
docker compose run web ./manage.py migrate
