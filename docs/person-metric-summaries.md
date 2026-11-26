# Person metric summaries

The global site metrics snapshot must not repeatedly aggregate the full
`app_showcrew` table. The table contains millions of credits, while the global
person metrics only need a small set of per-person facts.

## Stored data

`PersonMetricSummary` has one row per canonical person:

- distinct show types represented by that person's credits;
- distinct normalized Russian and English professions;
- source `Person` IDs with a credit on a show that has a valid Kinopoisk URL
  and no `ExternalRating` row.

The last field preserves the existing avatar metric's alias semantics: it
tracks source person IDs, not only canonical IDs. This lets the snapshot count
people waiting for Kinopoisk data without reading all credits.

`PersonMetricSummaryDirty` is a deduplicated work queue keyed by canonical
person ID. Database triggers mark affected people dirty when credits change,
show type or Kinopoisk URL changes, or an `ExternalRating` row is added,
removed, or moved. `PersonMetricSummaryState` records whether the initial
backfill completed. Snapshot jobs retry while the state is not ready.

## Refresh lifecycle

After applying migrations, run:

```sh
python manage.py rebuild_person_metric_summaries --batch-size 50000
```

The command takes the metrics snapshot, catalog write, and external rating
write locks. It rebuilds the summary in bounded canonical-ID ranges and marks
the state ready only after all ranges and queued changes are processed. It is
the one-time full pass; routine snapshot generation refreshes only dirty
people in small batches and aggregates the compact summary table.

If a rebuild fails, readiness remains false and snapshots defer. Resolve the
failure and rerun the command; it is safe to rerun because it clears and
rebuilds the summary.

## Consumers and freshness

The global snapshot uses this summary for profession counts, people by show
type, unused people, and the Kinopoisk-waiting part of avatar statistics.
Avatar totals that depend only on `Person` fields still count the `Person`
table directly.

Catalog tiles and detailed film cards continue to read their show data live.
Crew on a film detail page is fetched for that one `show_id`; it is not a
global aggregate and does not belong in this summary. Paginated person detail
lists and health reports also keep their own fresh database queries. In
particular, health-report checks must not use this summary or a cached global
snapshot.
