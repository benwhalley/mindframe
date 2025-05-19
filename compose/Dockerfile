FROM python:3.11.3-slim AS base
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

EXPOSE 8000

WORKDIR /app
COPY apt-packages /app

RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    gcc python3-dev git libpq-dev
RUN  xargs -a apt-packages apt-get install -y

# Create a non-root user for celery (UID 1000, GID 1000)
RUN addgroup --system --gid 1000 celery && \
    adduser --system --uid 1000 --gid 1000 celery

# Ensure `uv` installs dependencies system-wide
# first we install the dependencies from the lock file
COPY pyproject.toml uv.lock requirements.lock /app/
RUN uv pip install --system -r requirements.lock

# now we make sure any extras in the pyproject.toml are installed
# this shouldn't be necessary, but will help if we forget to update the requirements.lock file
# it also means rebuilding the container is faster as only new python packages are installed
RUN uv venv /app/.venv
RUN uv pip compile --output-file requirements-updated.lock pyproject.toml
RUN uv pip install -r requirements-updated.lock

# copy project code and settings
COPY . /app
RUN mkdir -p /app /app/static

# Ensure the installed packages are visible
RUN uv pip list && python -m site
