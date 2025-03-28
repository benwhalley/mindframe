# https://hub.docker.com/r/matrixdotorg/synapse

docker run -it --rm \
    --mount type=volume,src=synapse-data,dst=/data \
    -e SYNAPSE_SERVER_NAME=matrix.llemma.net \
    -e SYNAPSE_REPORT_STATS=yes \
    matrixdotorg/synapse:latest generate

docker run -d --name synapse \
    --mount type=volume,src=synapse-data,dst=/data \
    -p 8008:8008 \
    matrixdotorg/synapse:latest

docker exec -it synapse register_new_matrix_user http://localhost:8008 -c /data/homeserver.yaml --help
