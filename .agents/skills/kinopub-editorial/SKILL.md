---
name: kinopub-editorial
description: "Write, screenshot, structure, and publish KinoPub Observer help articles for search and AI discovery. Use for editorial content, GEO guidance, and article API publishing."
---

# KinoPub Editorial

Use this skill when creating or updating public KinoPub Observer guides. Produce helpful, accurate answers for people who want to manage films and series in Telegram; improve discoverability for search engines and answer engines through clear structure, useful evidence, and crawlable pages.

## Workflow

- Verify every described capability against the webapp before writing. Do not infer that a UI element implies an available action.
- Answer the reader's likely question in the opening paragraph, then give short, numbered steps, expected result, and relevant caveats. Use the language readers search in; avoid keyword repetition, generic filler, fake expertise, and claims that indexing or recommendation is guaranteed.
- Use real screenshots captured from the webapp in the browser iframe. For every multi-action guide, capture a distinct screenshot for each meaningful action and pair it with that step in one `step` block. A usual guide should have at least three action/evidence pairs; use fewer only when the task truly takes fewer actions. Do not reuse one screenshot across unrelated steps or articles.
- Capture the complete relevant screen at high resolution, wait for fonts and posters, and review every saved file's dimensions and crop before upload. A cropped strip, empty poster, blurry image, browser chrome, or viewport marker is a capture failure; retake it. Prefer a sharp portrait or landscape capture appropriate to the actual webapp view, then display it responsively without enlarging beyond its readable source size. Write factual Russian alt text and captions that identify the visible control and outcome. Never synthesize an interface and label it a screenshot.
- Write each action, its expected result, and its matching screenshot in a `step` block. Use short imperatives; separate actions into numbered steps, and show the confirmation state readers should see. Use `image` blocks only for contextual illustrations outside the procedure.
- Animate reading progress and reveal step panels with restrained, brief motion; do not use animation to convey information unavailable in text, and honor `prefers-reduced-motion`.
- Make each article independently useful and distinct. Add a stable lowercase slug, specific title and description, genuine publication timestamp with timezone, and a reviewable update date. Link related guides and the relevant bot entry point.
- Write content as typed JSON blocks: `lead`, `paragraph`, `heading`, `image`, `steps`, `list`, `callout`, and `quote`. The renderer escapes text. Never place raw HTML, JavaScript, or arbitrary image URLs in block content. Upload screenshots with the protected asset API and use its returned `/articles/assets/...` path.
- Publish through `PUT /api/internal/articles/<slug>/` with the existing `PUBLIC_ARTICLE_API_TOKEN` as a Bearer header. Never print, commit, or place the token in a URL or article. A null `published_at` keeps an article as a draft; use the configured token only, and stop if it is unavailable rather than inventing a credential.
- After publication, confirm the article is visible at its permanent URL, has one H1, canonical metadata, visible publication date, Article JSON-LD, working screenshots, links, and a sitemap entry. Keep the guide index limited to published content.

Read [references/editorial-and-api.md](references/editorial-and-api.md) for the block schema, publishing examples, and search-source guidance.
