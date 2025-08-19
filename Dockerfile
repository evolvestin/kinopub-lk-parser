FROM python:3.12-alpine

RUN addgroup -S app && adduser -S app -G app

RUN apk add --no-cache ca-certificates tzdata

WORKDIR /app

RUN mkdir /data && chown app:app /data

COPY --chown=app:app app/ /app/
RUN pip install --no-cache-dir -r requirements.txt

RUN chmod +x /app/main.py /app/healthcheck.py

USER app

ENV HEARTBEAT_FILE=/tmp/kinopub-parser_heartbeat \
    LOG_LEVEL=INFO

HEALTHCHECK --interval=30s --timeout=10s --retries=3 CMD python /app/healthcheck.py

CMD ["python", "/app/main.py"]