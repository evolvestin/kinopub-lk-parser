FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    tini \
    chromium \
    chromium-driver \
    tzdata \
    procps \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --gid 1000 app && adduser --uid 1000 --ingroup app --disabled-password --gecos "" app

RUN mkdir -p /home/app/bin && \
    cp /usr/bin/chromedriver /home/app/bin/chromedriver && \
    chown -R app:app /home/app

WORKDIR /app

RUN mkdir /data && chown app:app /data

COPY requirements.txt .
RUN pip install --no-cache-dir setuptools && \
    pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app . /app/

RUN python manage.py collectstatic --noinput

RUN chmod +x /app/manage.py

USER app

ENV PATH=/home/app/bin:$PATH \
    HEARTBEAT_FILE=/tmp/kinopub-parser_heartbeat \
    LOG_LEVEL=INFO \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=kinopub_parser.settings

ENTRYPOINT ["/usr/bin/tini", "--"]

HEALTHCHECK --interval=30s --timeout=10s --retries=3 CMD python /app/manage.py healthcheck