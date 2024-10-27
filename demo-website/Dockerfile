# syntax=docker/dockerfile:1.4
FROM python:3.11.3 AS builder
EXPOSE 5000
WORKDIR /app 

COPY apt-packages /app/
RUN apt-get update \
    && apt-get install -y gcc python3-dev musl-dev \
    && xargs -a apt-packages apt-get install -y \
    && apt-get clean

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
RUN pip3 install honcho
RUN pip3 install magentic
# RUN pip3 freeze

COPY . /app 
ENTRYPOINT [] 

# Create a non-root user and group
RUN groupadd -r appuser && useradd -r -g appuser appuser
# Change ownership of the application directory to the new user
RUN chown -R appuser:appuser /app
# Create home directory for appuser
RUN mkdir -p /home/appuser && chown -R appuser:appuser /home/appuser

# Switch to the non-root user
USER appuser
# Set the home environment variable
ENV HOME=/home/appuser


# CMD ["manage.py", "runserver", "0.0.0.0:8000"]
CMD cd src && honcho start