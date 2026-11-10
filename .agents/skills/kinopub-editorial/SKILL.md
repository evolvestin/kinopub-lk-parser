---
name: kinopub-editorial
description: "Write, screenshot, structure, and publish KinoPub Observer help articles for search and AI discovery. Use for editorial content, GEO guidance, and article API publishing."
---

# KinoPub Editorial

Use this skill when creating or updating public KinoPub Observer guides. Produce helpful, accurate answers for people who want to manage films and series in Telegram; improve discoverability for search engines and answer engines through clear structure, useful evidence, and crawlable pages.

## Workflow

- Verify every described capability against the webapp before writing. Do not infer that a UI element implies an available action.
- Answer the reader's likely question in the opening paragraph, then give short, numbered steps, expected result, and relevant caveats. Use the language readers search in; avoid keyword repetition, generic filler, fake expertise, and claims that indexing or recommendation is guaranteed.
- Use real screenshots captured from the webapp in the browser iframe. Prefer a 390×844 mobile viewport for the Telegram-style interface; keep the screen readable, wait for posters and fonts to load, and write descriptive Russian alt text and a caption. Do not synthesize a fake interface and label it a screenshot.
- Make each article independently useful and distinct. Add a stable lowercase slug, specific title and description, genuine publication timestamp with timezone, and a reviewable update date. Link related guides and the relevant bot entry point.
- Write content as typed JSON blocks: `lead`, `paragraph`, `heading`, `image`, `steps`, `list`, `callout`, and `quote`. The renderer escapes text. Never place raw HTML, JavaScript, or arbitrary image URLs in block content. Upload screenshots with the protected asset API and use its returned `/articles/assets/...` path.
- Publish through `PUT /api/internal/articles/<slug>/` with the existing `PUBLIC_ARTICLE_API_TOKEN` as a Bearer header. Never print, commit, or place the token in a URL or article. A null `published_at` keeps an article as a draft; use the configured token only, and stop if it is unavailable rather than inventing a credential.
- After publication, confirm the article is visible at its permanent URL, has one H1, canonical metadata, visible publication date, Article JSON-LD, working screenshots, links, and a sitemap entry. Keep the guide index limited to published content.

Read [references/editorial-and-api.md](references/editorial-and-api.md) for the block schema, publishing examples, and search-source guidance.
