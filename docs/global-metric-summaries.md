# Global metric summaries

Global site metrics should read small, incrementally maintained rollups instead
of repeatedly grouping millions of catalog and credit rows. The summaries are
refreshable read models: source tables remain authoritative, and the metrics
snapshot is their consumer.

## Catalog facts

`ShowMetricSummary` stores the metric flags and dimensions for one show.
`ShowMetricAggregate` stores grouped counts by metric, show type, year, and
status. The global snapshot reads the compact aggregate rows. It uses this for
catalog completeness counts such as missing ratings, metadata, genres,
countries, and durations.

Database triggers add affected show IDs to `ShowMetricSummaryDirty` when a
relevant `Show`, `ExternalRating`, `ShowDuration`, genre relation, or country
relation changes. At snapshot time, only dirty shows are recalculated and the
old and new aggregate contributions are applied as deltas. Writes that do not
change a fact used by these metrics do not enqueue work.

After migration, initialize once with:

```sh
python manage.py rebuild_show_metric_summaries --batch-size 50000
```

The command takes the metrics, catalog-write, and rating-write locks, performs
an indexed, bounded backfill, then builds the compact grouped counts. Until
that backfill succeeds, the metrics task defers instead of silently falling
back to the expensive full scans. The command is safe to rerun after a failed
backfill.

## Person facts

`PersonMetricSummary` stores normalized professions, show types, and source
person IDs with eligible Kinopoisk credits per canonical person.
`PersonMetricAggregate` stores the compact profession and show-type counts.
Changes to credits, show type, Kinopoisk URL/rating presence, or canonical
person links enqueue only affected canonical people for delta refresh.

Its initial backfill is documented in [person-metric-summaries.md](person-metric-summaries.md).

`PersonPhotoMetricSummary` and `PersonPhotoGroup` cover avatar counts and
unresolved duplicate-photo groups. The per-person flag rows maintain eight
avatar counters; `PersonKpWaitingSummary` indexes source person IDs whose
credits currently wait for a Kinopoisk lookup. Photo groups store counts by
source and URL, and Person writes enqueue only affected old/new URLs. The
snapshot refreshes those dirty people and URL groups before reading ten compact
counters; it no longer scans all people or groups on every run.

Dirty show facts are applied in bounded batches of 20,000 IDs. This keeps
ordinary updates incremental while draining large batches of catalog changes
with fewer repeated query/transaction cycles.

After migration, build them once after the person credit summary is ready:

```sh
python manage.py rebuild_person_photo_metric_summaries
```

The command takes the snapshot and catalog/rating write locks. Rebuilding the
person credit summary invalidates these dependent photo counters; run the
photo summary rebuild afterward.

## Freshness and page behavior

The summary tables are refreshed incrementally by database triggers and on the
next metrics snapshot. Global metric charts can therefore avoid full scans of
the catalog and person tables on every run. A periodic full rebuild remains
available to repair derived state.

The status strip keeps fresh timestamps and a rolling 24-hour error count. Its
large-table queries use partial B-tree indexes for the latest KP/IMDb sync,
photo fetch, parser completion, and recent errors. These indexes are created
concurrently so a release does not hold an exclusive table lock.

This does not apply to health reports: each health check must issue its own
fresh query. It also does not apply to a film card or catalog detail: those
pages read the selected show's current fields and credits by that show's ID,
not a global aggregate. Small reference-table counts (for example, the number
of genre or country dictionary rows) stay direct because they do not scan the
large catalog tables.

New large global aggregates should follow the same pattern: identify their
authoritative source rows, persist only the minimum per-entity facts needed,
mark changed entity IDs in the same transaction as source writes, and maintain
small grouped deltas. Avoid a second full-table scan in every snapshot and do
not use these rollups to answer unrelated detail or health queries.
