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


## Manual User Actions Policy

**RULE**: Actions initiated manually by the user via the WebApp (e.g., adding a view, rating, wishlist changes) MUST NOT trigger automated broadcasts to public or shared Telegram channels.

1.  **Reasoning**: Users should have the privacy to manage their data without forced public logging. Public channels are reserved for automated system events (like parser hits).
2.  **Implementation**: Use the `_skip_broadcast` attribute on model instances before saving to notify signal handlers that channel notifications should be suppressed.
3.  **Feedback**: Confirmation of manual actions must be sent directly to the user (private message) or displayed as UI feedback (Toasts/Modals), preferably via background tasks to keep the UI responsive.


## Media & Asset Loading Policy

**RULE**: Frontend must prioritize user experience by minimizing layout shifts and loading states through proactive preloading and intelligent fallback logic.

1.  **Image Source Priority**:
    *   Always attempt to load **TMDB** photos/posters first (highest quality, consistent sizing).
    *   Use **Kinopoisk** as the secondary fallback.
    *   Use the app's internal **SVG Placeholder** only if all external sources fail.

2.  **Kinopoisk "Fake Success" Detection**:
    *   **CRITICAL**: Kinopoisk often returns a `200 OK` with a "no-poster.gif" image instead of a `404`. 
    *   This image has fixed dimensions: **208x304** pixels.
    *   Implementation: Every image load event from a Kinopoisk source MUST check `naturalWidth` and `naturalHeight`. If they match 208x304, the image must be treated as a failure and replaced by the internal SVG placeholder.

3.  **Proactive Background Preloading**:
    *   Data and assets are not the same. When a JSON response with statistics or search results is received, the application must immediately start downloading the associated images in the background.
    *   This applies to hidden tabs (e.g., "Movies" tab in Actors leaderboards), items below the fold, and secondary scroll areas.
    *   Goal: By the time the user interacts (scrolls or switches tabs), the assets must already be in the browser cache.