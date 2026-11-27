# User statistics aggregates

## Purpose

Personal and group statistics are materialized per user and period. A normal
WebApp request reads an already-built row instead of running the statistics
aggregation against viewing history, ratings, and wishlist data again.

The materialization avoids repeated work on reads. A background rebuild still
aggregates the affected user's source records after relevant data changes; it
does not scan the whole catalog to serve a statistics page.

## Storage model

`app.models.UserStatsAggregate` has one row for a `(user, scope, year)` tuple:

| Field | Meaning |
| --- | --- |
| `user` | Owner of the personal statistics, or the user whose group view is being shown |
| `scope` | `personal` or `group` |
| `year` | Calendar year; `NULL` means all time |
| `aggregates` | Summary values, charts, favorites, metadata, and other compact calculated results |
| `details` | History projections such as movie/episode entries and rating history |
| `ready` | Whether a complete result has been built at least once |
| `dirty` | Whether source data changed after the last completed build |
| `dirty_version` | Version counter used to detect writes that happen during a rebuild |
| `generated_at` | Time of the most recent successful save |

The unique constraint `uniq_user_stats_aggregate_period` covers `(user, scope,
year)` and treats `NULL` years as equal (`nulls_distinct=False`). This gives each
user/scope exactly one all-time row as well as at most one row for each year.
The same constraint supplies the B-tree index used by the indexed period
lookups.

The Django model and schema migration are in `app/models.py` and
`app/migrations/0111_user_stats_aggregate.py`.

## Write and refresh lifecycle

Relevant data changes call `mark_user_stats_aggregates_dirty(user_id, year)`.
The invalidation updates or creates the applicable rows and queues refreshes
after the surrounding database transaction commits.

* When a specific year is known, that year's row and the all-time row become
  dirty. Other yearly rows remain ready.
* When the year is unknown, all existing periods for the affected scope are
  marked dirty, along with the all-time row.
* Personal statistics are always affected. Existing group rows are affected,
  and a user who currently belongs to a group also gets group-scope rows.
* Repeated invalidations are coalesced in Redis by user, scope, and year. The
  key expires after 15 minutes; the queued Celery task expires after 10 minutes.
* The refresh task runs on the `metrics` queue. It calculates only the given
  user's scope and period, saves the result, and logs elapsed time, query count,
  total SQL time, and the slowest SQL statement.
* If source data changes while a task is building a row, `dirty_version` no
  longer matches the version the task started with. The saved row stays dirty
  and another refresh is queued after the current task finishes.

The current invalidation hooks cover:

* Viewing history save/delete and changes to the users attached to a history
  item. A known viewing date invalidates that year and all time. Moving a
  history item to another year invalidates both its previous and new years.
* Rating save/delete. The rating's viewing years, update year, and all-time
  statistics are invalidated.
* Group membership add/remove/clear and group updates. Affected group
  statistics are invalidated for the members.
* WebApp wishlist and casino operations, which invalidate the user's
  statistics explicitly.

When adding or changing a write path that affects displayed user statistics,
make sure it invalidates the applicable aggregate rows. Django bulk updates
that bypass model signals must call the invalidation helper explicitly.

## Read behavior

### Current or selected period

`POST /api/webapp/detailed_stats/` calls `generate_user_stats()` for the
selected year (or all time). If a ready aggregate exists, the function reads
that row and reconstructs the API payload from `aggregates` and `details`.
If the row is dirty, the last ready result is returned immediately and a
background refresh is queued. This is stale-while-revalidate behavior: a user
does not wait for a rebuild after every write. The bulk historical-period
endpoint omits dirty rows until their refresh finishes.

The group payload uses the same per-user/year table with `scope='group'`. The
common personal request avoids loading group history unless the group tab is
requested; a small `meta.has_group` flag tells the frontend whether the group
tab is available.

### Other years

After the selected period loads, the frontend sends the other available years
to `POST /api/webapp/detailed_stats_periods/` in one request. The endpoint
limits a request to 50 periods and reads the requested rows with one ORM query
filtered by user, scope, and year. Ready rows are returned together. Missing,
not-yet-ready, or dirty periods are queued for background refresh and listed in
`pending_periods`; already-ready years are still returned in the same response.
The frontend keeps those ready years and polls while the rest are being built.

This makes the usual statistics-page read path two database reads: one for the
selected period, then one bulk indexed read for the other requested periods.
The first cold read can additionally enqueue background work. A cold selected
period returns HTTP 202 with `{"pending": true}` when the frontend opts into
`allow_background_build`; the frontend polls that endpoint every five seconds.
Historical bulk periods are polled every ten seconds. Callers that do not opt
into background builds retain the synchronous calculation path for a missing
aggregate.

## Initial population and ongoing maintenance

Rows are created as needed by invalidation and by aggregate generation. The
periodic `precalculate_all_stats` task schedules the current year and all-time
statistics for active viewers and administrators. Older years are built on
demand when the frontend prefetches them; after that, writes to an existing
year keep that year and all time up to date.

There is no catalog-wide user-statistics scan on the page-read path. A cold
build or a post-write refresh can still query the affected user's own history,
ratings, and wishlist to produce a complete result. Those builds run in the
background when requested through the WebApp's background-build flow.

## Verification and performance claims

`app.test_stats_aggregate` verifies that:

* a clean period is served with one aggregate-row query and does not run the
  calculation;
* a dirty result is served while one refresh is queued;
* a change dirties the affected year and all-time row, but not unrelated years;
* multiple ready years are loaded with one query; and
* missing years are queued, while ready years can be returned in the same bulk
  response.

These checks establish query count and refresh behavior, not a 50 ms latency
guarantee. Actual latency depends on database location, row size, network, and
JSON payload serialization and must be measured against representative data.

## Code map

* Model and constraint: `app/models.py` — `UserStatsAggregate`.
* Schema: `app/migrations/0111_user_stats_aggregate.py`.
* Queueing, invalidation helper, serialization, and period reads:
  `app/services/stats_calculator.py`.
* Data-change signals: `app/signals.py`.
* Background refresh and periodic precomputation: `app/tasks.py`.
* WebApp endpoints and URL routes: `app/views.py`, `kinopub_parser/urls.py`.
* Frontend polling and historical-year prefetch:
  `frontend_webapp/src/stores/useStatsStore.js`.
