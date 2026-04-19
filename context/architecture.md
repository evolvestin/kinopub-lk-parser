# Architectural Rules for AI/LLM

## Data Integrity Principle: Raw-First Approach

**CRITICAL RULE**: Do NOT filter, normalize, or sanitize data BEFORE it enters the database.

1.  **Parsers (Scrapers/API Clients)**:
    *   Must save data exactly as received from the source (Kinopub, Poiskkino, etc.).
    *   Forbidden: `.lower()`, `.strip()`, or deduplication logic during the `create` or `bulk_create` phase.
    *   Reason: The database must act as a raw mirror of the source.

2.  **Rationale**:
    *   Preservation of source history.
    *   Ability to re-run normalization logic without re-scraping data if business rules change.
    *   Prevention of data loss caused by over-aggressive pre-filtering.

Any code generating new database records must follow this "Save-As-Is" architecture.


## Display-Level Normalization Policy

**RULE**: For entities like Genres, where the source data frequently contains case duplicates or trailing spaces, normalization MUST be performed at the application layer (Python or ORM queries) rather than cleaning the database.

1.  **Single Source of Truth**: All normalization logic for specific fields must reside in `app/utils.py`.
2.  **Implementation**:
    *   Use `get_genre_norm()` for Django QuerySets (aggregations, counts, group by).
    *   Use `normalize_genre_name()` for Python-side processing (properties, list filtering).
3.  **Metrics Consistency**: Any metric displayed on the dashboard that counts "Unique" items must apply these normalization functions to avoid reporting duplicates caused by casing differences.