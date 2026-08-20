# Metrics and duplicate-person rollout

1. Take a PostgreSQL backup and deploy the application image containing migrations `0072`–`0074`.
2. Run `python manage.py migrate --noinput`. Migrations `0073` and `0074` create partial indexes
   concurrently, so it does not take an exclusive table lock.
3. Let the scheduled `syncpoiskkinoratings` run complete once. It records whether KinoPoisk
   actually publishes a rating, clears stale values, and separates checked-but-unrated titles
   from synchronization errors. Until that pass completes, pre-existing unrated records remain
   deliberately unclassified rather than being reported as errors.
4. Rebuild the global snapshot after the sync by waiting for the next hourly Celery task, or enqueue
   it immediately with:
   `python manage.py shell -c "from app.tasks import update_site_metrics_task; update_site_metrics_task.delay()"`.
5. Validate the deployment:

   ```sh
   python manage.py verify_metric_details
   python manage.py benchmark_metric_details --case missing_kp=Movie --case kp_unrated=Movie \
     --case duplicate_photo_urls=TMDB --case duplicate_photo_urls=KP --offsets 0,50
   ```

   A warm detail page should be in the low-millisecond range. Investigate a consistent result
   above 100 ms; a first request can include Django URL resolver initialization.

6. Do not mass-merge actor records solely by identical image. A shared photo is evidence, not an
   identity. The dashboard now excludes groups whose members already have distinct TMDB IDs.
   For aliases without TMDB IDs, inspect the strict automatic rule first:

   ```sh
   python manage.py merge_verified_kp_person_aliases --min-common-shows 2
   ```

   It requires exactly two rows, the same KP photo, the same normalized English name, no TMDB IDs,
   no conflicting TMDB photos, and at least two common titles. Apply reviewed candidates with
   `--apply`, then run `python manage.py backfillcanonicalperson --no-indexes`.
