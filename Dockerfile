# Use Alpine-based Python image
FROM python:3.11-alpine

# Environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CRON="0 2 * * *"

# Working directory
WORKDIR /app

# Install bash, cron, git, tzdata, and build dependencies
RUN apk add --no-cache \
        bash \
        git \
        dcron \
        tzdata \
        build-base \
        musl-dev \
        libffi-dev \
        python3-dev \
        py3-pip
        ffmpeg

# Copy requirements if you build from local
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy entrypoint
COPY docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose logs
VOLUME ["/var/log"]

ENTRYPOINT ["/entrypoint.sh"]