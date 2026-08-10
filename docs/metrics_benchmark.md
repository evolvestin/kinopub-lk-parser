# Metric detail benchmark

The benchmark exercises the same Django endpoint used by the metrics detail modal. It reports
wall-clock time, SQL query count, response size, returned item count, and whether another page is
available. The default cases include a large show detail, a queueable detail, and duplicate photo
groups.

Run it against the local production-sized database:

```sh
docker compose exec -T web python manage.py benchmark_metric_details
```

Custom cases use the API metric key and the value sent as the `type` query parameter:

```sh
docker compose exec -T web python manage.py benchmark_metric_details \
  --case missing_durations=Movie \
  --case duplicate_photo_urls=TMDB \
  --offsets 0,50,100 --limit 50
```
