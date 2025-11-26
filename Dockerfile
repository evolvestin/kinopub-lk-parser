FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    tzdata \
    procps \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --system app && adduser --disabled-password --ingroup app --gecos "" app

RUN mkdir -p /home/app/bin && \
    cp /usr/bin/chromedriver /home/app/bin/chromedriver && \
    chown -R app:app /home/app

WORKDIR /app

RUN mkdir /data && chown app:app /data

COPY --chown=app:app . /app/

RUN pip install --no-cache-dir setuptools
RUN pip install --no-cache-dir -r requirements.txt

RUN python manage.py collectstatic --noinput

RUN chmod +x /app/manage.py

USER app

ENV PATH=/home/app/bin:$PATH \
    HEARTBEAT_FILE=/tmp/kinopub-parser_heartbeat \
    LOG_LEVEL=INFO \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=kinopub_parser.settings

HEALTHCHECK --interval=30s --timeout=10s --retries=3 CMD python /app/manage.py healthcheck