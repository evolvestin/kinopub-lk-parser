# Editorial format and API

## GEO and useful answer pages

Treat GEO as clear, verifiable publishing, not a separate keyword trick. A guide should:

- Put the exact task and its short answer near the top.
- Use one descriptive H1 and task-oriented H2 headings. Cover one main question per URL; connect related pages with useful internal links.
- Explain the actual controls and outcome in the current webapp. State prerequisites and exceptions instead of promising that every user will see a notification or result.
- Write a procedure as one numbered action per step, in the order the reader performs it. Include where to act, what to do, and the confirmation or result that follows.
- Pair every meaningful action with its own unique browser screenshot inside the same step block. A normal multi-action guide should show at least three different states (start, action, result) and use a separate shot for each meaningful stage. Never reuse a generic screenshot to fill out a procedure or reuse the same asset across unrelated articles.
- Capture the complete relevant browser iframe screen at sharp native resolution; verify each image's dimensions, legibility, and crop. Reject clipped, tiny, blurry, empty, or wrong-state captures before publishing. Add concise, factual Russian captions and alt text that say what is visible. Do not use stock images as UI evidence.
- Show the outcome immediately after the actions, then add a short check/troubleshooting note only when it solves a likely failure.
- Show a real publication date and update date. Keep metadata and visible dates consistent; do not backdate or invent an author.
- Use `Article` structured data with the organization as author/publisher, headline, description, canonical page, and relevant screenshot URLs. Structured data should match visible article content.
- Keep pages crawlable: stable URL, self canonical, normal HTML text, public images, sitemap listing, and no `noindex` on public article URLs. Never add API tokens or private preview URLs to rendered metadata.
- Optimize screenshots before upload when it preserves legibility. Set width/height or aspect ratio in the markup, lazy-load non-hero images, and use immutable cache headers on content-hashed image paths.
- Do not promise a Google ranking, inclusion in an AI answer, or a fixed indexing time. Allow OAI-SearchBot if the owner wants ChatGPT search discovery; this is separate from GPTBot and does not guarantee citations.

Primary references checked 2026-11-10:

- Google Search: [Creating helpful, reliable, people-first content](https://developers.google.com/search/docs/fundamentals/creating-helpful-content)
- Google Search: [Article structured data](https://developers.google.com/search/docs/appearance/structured-data/article)
- Google Search: [Publication and update dates](https://developers.google.com/search/docs/appearance/publication-dates)
- OpenAI: [Search crawlers and OAI-SearchBot](https://developers.openai.com/api/docs/bots)
- OpenAI: [Publisher and developer FAQ](https://help.openai.com/en/articles/12627856-publishers-and-developers-faq)

## Article block schema

```json
{
  "title": "Как добавить сериал в избранное и включить уведомления",
  "description": "Пошагово: найдите сериал, сохраните его в папку и проверьте настройки уведомлений.",
  "published_at": "2026-11-10T12:00:00+03:00",
  "content_blocks": [
    {"type":"lead","text":"Короткий прямой ответ на запрос читателя."},
    {"type":"heading","text":"Добавьте сериал в папку"},
    {"type":"step","title":"Откройте поиск","text":"В нижней панели приложения выберите «Поиск».","result":"Откроется экран поиска.","image":{"src":"/articles/assets/slug/step-01.jpg","alt":"Раздел поиска выбран в нижней панели","caption":"Шаг 1. Перейдите к поиску."}},
    {"type":"step","title":"Найдите сериал","text":"Введите точное или оригинальное название и выберите подходящий результат.","image":{"src":"/articles/assets/slug/step-02.jpg","alt":"Введён запрос и показаны результаты поиска","caption":"Шаг 2. Сверьте название и год выпуска."}},
    {"type":"step","title":"Выберите папку","text":"В карточке сериала добавьте его в избранное и укажите нужную папку.","result":"Сериал появится в выбранной папке.","image":{"src":"/articles/assets/slug/step-03.jpg","alt":"Сериал отображается в выбранной папке избранного","caption":"Шаг 3. Проверьте результат в избранном."}},
    {"type":"paragraph","text":"Пояснение, ограничение или ожидаемый результат."},
    {"type":"callout","text":"Важно: откройте чат с ботом и убедитесь, что он не заблокирован."},
    {"type":"list","items":["Что проверить, если…"]},
    {"type":"quote","text":"Краткое правило или практический совет."}
  ]
}
```

Supported block types are `lead`, `paragraph`, `heading`, `image`, `step`, `steps`, `list`, `callout`, and `quote`. A `step` stores title, action text, optional result, and its matching image object (`src`, `alt`, `caption`, optional dimensions). Text fields and list items are escaped by Django. Every image `src` must be returned by the asset endpoint. The article API accepts up to 2 MB of JSON; image upload is limited to 12 MB and supports PNG, JPEG, and WebP.

## Publish securely

Upload each browser screenshot as multipart field `image`:

```sh
curl -X POST "https://SITE/api/internal/articles/assets/SLUG/" \
  -H "Authorization: Bearer $PUBLIC_ARTICLE_API_TOKEN" \
  -F "image=@SCREENSHOT.jpg"
```

Use the returned `src` in an `image` block, then submit the article:

```sh
curl -X PUT "https://SITE/api/internal/articles/SLUG/" \
  -H "Authorization: Bearer $PUBLIC_ARTICLE_API_TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary @article.json
```

Keep the token in the environment or a secret manager. Never echo it, include it in a shell command literal, store it in a file tracked by Git, or append it to a URL. If it is not configured in the target environment, leave the article as a draft and report the configuration blocker; do not generate a new key implicitly.
