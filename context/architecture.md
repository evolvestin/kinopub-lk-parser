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


## Display-Level Translation Policy

**RULE**: All user-facing metadata fields, specifically `type` (e.g., "Series", "Movie", "3D Movie") and `status` (e.g., "Finished", "Ongoing"), MUST be translated to Russian at the display layer before rendering in the UI.

1.  **Rationale**: The database stores raw strings from the source (e.g., "Series", "Finished") to preserve data integrity and prevent breaking any internal English-based backend or frontend conditional logic.
2.  **Implementation**:
    *   On the Python/Backend side (for bot cards, notifications, reports), translation maps `SHOW_TYPE_DISPLAY_RU` and `SHOW_STATUS_DISPLAY_RU` from `shared/constants.py` must be used.
    *   On the Frontend side (Vue/JS), raw English strings from the API must be dynamically translated using helper functions or computed properties before rendering to avoid layout-shifts or displaying raw values.


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
    *   Data and assets are not the same. When a JSON response with statistics, search results, or show details is received, the application must immediately start downloading the associated images in the background.
    *   This applies to hidden tabs (e.g., "Movies" tab in Actors leaderboards), items below the fold, secondary scroll areas, and the actors/crew horizontal scroll inside the show details view.
    *   Goal: By the time the user interacts (scrolls, switches tabs, or opens a list), the assets must already be in the browser cache.

## State Persistence & Routing Policy

**RULE**: All UI states (selected year, active tab, active folder, search query, active sort/view modes, and currently open modals with their contexts and internal form states) MUST be persisted and synchronized via URL path and query parameters using `vue-router`.

1. State representation:
    *   **Layers** (show details, collections, history) are represented as path segments: `/:base_view/:layer_type/:layer_id/...`.
    *   **Filters and tabs** are stored as query parameters:
        *   `y` - Selected year (`all` or year string).
        *   `tab` - Selected statistics tab (`personal` or `group`).
        *   `folder` - Selected wishlist folder ID.
        *   `sort` - Wishlist sort mode.
        *   `view` - Wishlist/History view mode.
        *   `q` - Active search query.
    *   **Modals** are stored as query parameters starting with `modal_`:
        *   `modal` - Name of the currently open modal.
        *   `modal_showId`, `modal_title`, `modal_type`, `modal_folderId`, `modal_isEdit`, etc. - Context values for the active modal.
        *   **Modal Form/Internal States** - All user inputs, toggles, active sub-levels, selected items, ratings, and date selections inside modals must also use the `modal_` prefix (e.g., `modal_level`, `modal_val`, `modal_season`, `modal_episode`, `modal_dateMode`, `modal_exactDate`, `modal_name`, `modal_color`, `modal_icon`, `modal_years`, `modal_anon_user`, `modal_include_group`, `modal_anon_group`, `modal_keepStats`).

2. Synchronization Implementation:
    *   Do NOT use `localStorage` or `sessionStorage` for storing transient UI state like year, active tab, folder, or modal contexts.
    *   Stores (Pinia) and modal components must initialize their states by reading from the current route's query parameters on boot or on route changes.
    *   When store or component state changes, the query parameters must be updated reactively via `router.replace` (to avoid polluting the browser back button history with minor state changes).
    *   To prevent redundant navigation calls and routing race conditions, always batch multiple state updates into a single `router.replace` call.
    *   For high-frequency UI updates (such as dragging a rating slider), the synchronization of value updates to query parameters must be debounced.


## Local Safety & Backup Policy

**RULE**: Local and development environments are permitted to synchronize session cookies to maintain shared authentication, but must never overwrite the production database backup on Google Drive.

1. **Implementation**:
    * In `perform_backup`, database upload to Google Drive must be skipped if `settings.ENVIRONMENT` is `'DEV'` or if `settings.LOCAL_RUN` is `True`.
    * Cookie backups and restores (`perform_cookies_backup` and `restore_from_backup`) remain fully functional across environments to ensure unified session states.


## Internal Rating Calculation Policy

**RULE**: The overall internal rating (LocalRating / LR) of a show must be computed exclusively in a single, centralized place: the `get_internal_rating_data` method of the `Show` model in `app/models.py`.

1.  **Centralization**:
    *   No view, task, bot handler, or external module is permitted to compute the average or median of internal ratings directly using inline aggregation or custom Python loops. They must always invoke `show.get_internal_rating_data()`.
2.  **Algorithm Selection (Hybrid Mean-Median)**:
    *   The rating calculation utilizes a two-step hybrid approach: first, averaging multiple ratings from the same user (e.g., episode-level ratings) to obtain a per-user score.
    *   Second, it computes a weighted combination of the arithmetic mean and the median of these per-user scores. 
    *   At 1 vote, the rating is 100% arithmetic mean. It smoothly transitions to 100% median over 20 votes. This ensures high sensitivity/responsiveness for small groups (to prevent rating "sticking") while automatically providing robust resistance against outliers/troll votes as the community grows.


## Data Preloading Policy

**RULE**: To guarantee an instantaneous and fluid user experience, the application MUST proactively prefetch core business data in the background during the initial application bootstrap, rather than waiting for the user to navigate to specific views.

1.  **Global Wishlist Prefetching**:
    *   The global wishlist dataset (`wishlistStore.fetchWishlist()`) MUST be initiated inside the root application component (`App.vue` on mounted) parallel to the initial statistics.
    *   This ensures that when the user switches to the "Wishlist" tab, all folders and their corresponding items are already cached in the Pinia store, eliminating any visual layout shifts or loading spinners.

2.  **Stat Cache Maintenance**:
    *   Prefetched data must be kept in memory/Pinia state to act as a local cache.
    *   Subsequent view transitions must rely on this cache first, triggering background updates (`force` refresh) only when explicitly required by user interactions (e.g., modifying folders or rating changes).