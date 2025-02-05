
# dump and copy locally
ssh az1 sudo docker exec -i postgres pg_dump -O -f mindframe.dump -F c -d mindframe -h 127.0.0.1 -p 5432 -U postgres && \
    ssh az1 sudo docker cp postgres:/mindframe.dump mindframe.dump && \
    scp az1:mindframe.dump mindframe.dump



# restore

docker cp mindframe.dump mindframe-postgres-1:/mindframe.dump

docker exec -it mindframe-postgres-1  dropdb mindframe -U postgres
docker exec -it mindframe-postgres-1 create-database.sh mindframe mindframe mfpassword
docker exec -it mindframe-postgres-1 pg_restore -v -U postgres -d mindframe /mindframe.dump
docker exec -it mindframe-web-1 ./manage.py migrate
