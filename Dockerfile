# Этап 1: Сборка фронтенда
FROM node:20-alpine AS build-stage
WORKDIR /app/frontend_webapp
COPY frontend_webapp/package*.json ./
RUN npm install
COPY frontend_webapp/ ./
# Копируем внешние зависимости стилей, которые импортируются во фронтенд
COPY kinopub_parser/static/css/ /app/kinopub_parser/static/css/
RUN npm run build

# Этап 2: Основной образ Python
FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    tini \
    tzdata \
    procps \
    postgresql-client \
    curl \
    ca-certificates \
    && curl -sS -o /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get install -y --no-install-recommends /tmp/chrome.deb \
    && rm /tmp/chrome.deb \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --gid 1000 app && adduser --uid 1000 --ingroup app --disabled-password --gecos "" app

RUN mkdir -p /home/app/bin && \
    chown -R app:app /home/app

WORKDIR /app

RUN mkdir /data && chown app:app /data

COPY requirements.txt .
RUN pip install --no-cache-dir setuptools && \
    pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app . /app/

# Копируем собранный фронтенд из первого этапа в безопасную директорию вне /app
COPY --from=build-stage --chown=app:app /app/frontend_webapp/dist /home/app/frontend_dist_backup
COPY --from=build-stage --chown=app:app /app/frontend_webapp/dist /app/frontend_webapp/dist

RUN python manage.py collectstatic --noinput

RUN chmod +x /app/manage.py

USER app

ENV PATH=/home/app/bin:$PATH \
    HEARTBEAT_FILE=/data/heartbeat \
    LOG_LEVEL=INFO \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=kinopub_parser.settings

ENTRYPOINT ["/usr/bin/tini", "--"]

HEALTHCHECK --interval=30s --timeout=10s --retries=3 CMD python /app/manage.py healthcheck