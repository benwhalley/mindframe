# Developing and Running Mindframe Locally

This repo includes code and instructions to set up mindframe for local development using Docker.

See `init-project.sh`

Then the sites are running:

```sh
open http://127.0.0.1:8080/admin
open http://127.0.0.1:8080/start/demo/  # for the chatbot
```

And follow the logs:

```sh
docker logs -f mindframe-chat-1
docker logs -f mindframe-web-1
```



## Developing/editing the mindframe package

The generated `docker-compose.yml` bind-mounts
`~/dev/mindframe/mindframe` to `/app/mindframe` in the container.
This means that the container uses the local copy of the mindframe package code.
, and installs it with `pip install -U -e` as the  container loads, making it editable.

The docker uses watchdog/watchme to reload code changes automatically.

HOWEVER, changes to pyproject.toml/poetry.lock are only visible after the container is rebuilt with

`docker-compose down && docker-compose up -d --build`


Also note that changes to Env vars won't not be reflected in the running server.
You will need to recreate docker-compose.yml (see init script) and restart the containers.



## Rebuilding the containers

To rebuild:

```sh
docker-compose  down && docker-compose up -d --build
```

Or to force a rebuild without using the docker cache:

```sh
docker-compose down
docker image prune -f
docker-compose build --no-cache
docker-compose up -d
```



## Fixtures

To remake the fixtures from current data, select these models and use a docker container to dump the data into the fixtures folder in the editable package folder:

```sh
docker-compose run web \
	./manage.py dumpdata \
	mindframe.Nudge \
	mindframe.Intervention \
	mindframe.Step \
	mindframe.StepJudgement \
	mindframe.Transition \
	mindframe.Judgement \
	llmtools.LLM \
	--indent 2 \
	--natural-foreign --natural-primary  \
	--format=json > ~/dev/mindframe/mindframe/fixtures/demo.json

```




# Using docker-compose


```bash
docker-compose -f base.yml  -f ~/dev/mindframe-staging/compose/staging.yml config  > STAGING__.yml

docker-compose -f base.yml  -f ~/dev/mindframe/compose/production.yml config  > PRODUCTION__.yml


docker-compose -f STAGING__.yml build base

docker-compose -f STAGING__.yml run web ls

docker-compose -f PRODUCTION__.yml build base

docker-compose -f STAGING__.yml stop web
docker-compose -f STAGING__.yml up --build -d web


```


# Dropping the database

```sh
# docker exec -t mindframe-postgres-1 dropdb -U postgres mindframe
```
