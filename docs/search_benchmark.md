# Search benchmark

The production search paths use substring matching (`icontains`) for show titles,
original titles, people names, and the admin show plot search. The benchmark runs
the same ORM shapes against the local PostgreSQL copy so index changes can be
compared on the real data volume.

Run from the project root:

```text
docker compose exec -T web python manage.py benchmark_search --repeat 7 --warmup 2
```

Useful variants:

```text
docker compose exec -T web python manage.py benchmark_search --query matrix --query дюна --repeat 10
docker compose exec -T web python manage.py benchmark_search --query zzzz-no-match --no-explain
```

Scenarios:

- `webapp_shows`: webapp title/original-title search with ordering and pagination;
- `webapp_persons`: webapp person-name search and its `updated_at` ordering;
- `bot_shows`: bot title/original-title search with a 20-item limit;
- `admin_shows`: admin title/original-title/plot search, including the result count and first page.

The command also prints a compact `EXPLAIN ANALYZE` plan for each scenario. Record
`min`, `p50`, and `p95` after each schema change; the first run is the baseline.

## Local run log

The following runs used `repeat=3`, `warmup=1`, and the default page sizes on the
local copy containing roughly 1.35 million shows and 3.10 million people:

| Query | Scenario | Baseline p50 | Indexed p50 |
| --- | --- | ---: | ---: |
| `matrix` | webapp shows | 616 ms | 1.4 ms |
| `matrix` | webapp people | 453 ms | 2.2 ms |
| `matrix` | bot shows | 131 ms | 1.0 ms |
| `matrix` | admin shows | 1104 ms | 2.7 ms |
| `дюна` | webapp shows | 761 ms | 0.7 ms |
| `дюна` | webapp people | 463 ms | 0.6 ms |
| `дюна` | bot shows | 264 ms | 0.5 ms |
| `дюна` | admin shows | 1183 ms | 1.6 ms |
| `zzzz-no-match` | webapp shows | 513 ms | 4.2 ms |
| `zzzz-no-match` | webapp people | 483 ms | 2.6 ms |
| `zzzz-no-match` | bot shows | 267 ms | 4.1 ms |
| `zzzz-no-match` | admin shows | 1020 ms | 8.3 ms |

Short one- or two-character terms remain less selective for PostgreSQL trigram
search. They are still much faster for show/bot results, but broad person/admin
queries can approach 0.5 seconds because PostgreSQL must inspect many matches and
sort/count them. The webapp already avoids queries shorter than two characters.
