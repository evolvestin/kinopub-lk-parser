# Metrics and duplicate-person rollout

1. Take a PostgreSQL backup and deploy the application image containing migrations `0072`–`0074`.
2. Run `python manage.py migrate --noinput`. Migrations `0073` and `0074` create partial indexes
   concurrently, so it does not take an exclusive table lock.
3. Let the scheduled `syncpoiskkinoratings` run complete once. It records whether KinoPoisk
   actually publishes a rating, clears stale values, and separates checked-but-unrated titles
   from synchronization errors. Until that pass completes, pre-existing unrated records remain
   deliberately unclassified rather than being reported as errors.
4. The Poiskkino and person-photo tasks invalidate the duplicate-photo cache after their
   transaction commits and queue a global snapshot refresh after releasing the catalog lock.
   For a manual sync, enqueue the refresh only after the writer has finished:
   `python manage.py shell -c "from app.tasks import update_site_metrics_task; update_site_metrics_task.delay()"`.
   Check the snapshot timestamp before treating the dashboard value as current.
5. Validate the deployment:

   ```sh
   python manage.py verify_metric_details
   python manage.py benchmark_metric_details --case missing_kp=Movie --case kp_unrated=Movie \
     --case duplicate_photo_urls=TMDB --case duplicate_photo_urls=KP --offsets 0,50
   ```

   A warm detail page should be in the low-millisecond range. Investigate a consistent result
   above 100 ms; a first request can include Django URL resolver initialization.

6. Kinopoisk person identity uses the exact usable `kp_photo_url` as the catalog identity. If a
   new source KP ID arrives with an existing KP photo, the sync must keep the source ID on an
   alias row linked to the existing canonical `Person`; it must not create another root person.
   Existing duplicate root rows are not deleted automatically and remain visible to the metric
   until they are explicitly reconciled. The duplicate-photo metric itself must not be weakened
   or filtered: it is the alarm for unresolved groups.

   This rule is only for Kinopoisk. TMDB matching remains `tmdb_id`-first; a shared
   `tmdb_photo_url` is only a review candidate when the TMDB identity is unresolved. Never apply
   the KP-photo alias rule to TMDB records.

   For existing aliases, inspect the reconciliation command first:

   ```sh
   python manage.py merge_verified_kp_person_aliases --min-common-shows 2
   ```

   Apply only reviewed candidates with `--apply`, then run
   `python manage.py backfillcanonicalperson --no-indexes`.

7. Do not use the persisted global snapshot as a substitute for a fresh health-report query.
   Every health-report metric must execute its own independent database query. The dashboard
   snapshot is a presentation cache and must show its generation time; if a catalog writer is
   active, the metrics task retries after the writer releases `CATALOG_WRITES`.
