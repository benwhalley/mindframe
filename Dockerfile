FROM python:3.11.3-slim AS base
EXPOSE 8000

WORKDIR /app

COPY apt-packages /app
RUN apt-get update \
    && apt-get install  --no-install-recommends  -y \
    gcc python3-dev git libpq-dev \
    && xargs -a apt-packages apt-get install -y \
    && apt-get clean

RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir poetry
RUN poetry config virtualenvs.create false

COPY poetry.lock pyproject.toml /app
RUN poetry install --no-root -vvv
RUN pip install --no-cache-dir ruamel.yaml
RUN pip install --no-cache-dir watchdog[watchmedo]

RUN mkdir -p /app /app/static
COPY . /app
WORKDIR /app
