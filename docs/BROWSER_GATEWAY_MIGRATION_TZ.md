# ТЗ: перенос браузера Kinopub в AssetHub Browser Gateway

## Цель

Убрать запуск Chromium из Kinopub и исключить параллельные Selenium-процессы
на сервере. Все браузерные операции Kinopub выполняются единственным
`browser-gateway` worker внутри AssetHub.

## Контракт интеграции

Kinopub задаёт:

```dotenv
BROWSER_GATEWAY_URL=http://assethub-backend:8000
BROWSER_GATEWAY_TOKEN=<тот же секрет, что в AssetHub>
BROWSER_GATEWAY_TASK_TIMEOUT_SECONDS=900
```

Перед первым действием создаётся сессия с `profile_key` `kinopub-main` или
`kinopub-aux`. API возвращает `session_id` и `task_id` операции `open`.
Операции передаются как задачи и имеют статусы `queued`, `processing`,
`succeeded`, `failed`. Внутренний клиент Kinopub ждёт завершения, поэтому
остальной парсер продолжает работать с Selenium-подобным объектом.

## Перенос функциональности

Существующие сценарии сохраняются: login, 2FA через email processor, проверка
Cloudflare, история просмотров, новые эпизоды, full scan, gap scanner,
обновление деталей и длительностей. Их DOM-парсеры остаются в Kinopub, а
вызовы `get`, `find_element(s)`, `execute_script`, действия элементов и
получение `page_source` уходят в очередь AssetHub.

Kinopub больше не должен:

- импортировать или запускать `undetected_chromedriver`;
- вызывать `pkill chromium/chromedriver`;
- создавать `uc_browser_data_*`;
- читать, писать, удалять или загружать в Google Drive `cookies_main.json` и
  `cookies_aux.json`.

## Cookies и аккаунты

AssetHub хранит единый `/data/browser/cookies.json`, разделённый по
`profile_key`. Это один файл для Kinopub и будущих проектов, но cookies
основного и auxiliary аккаунтов Kinopub не смешиваются. После login, навигации,
изменения cookie или закрытия сессии gateway атомарно обновляет vault.

## Приёмка

1. При двух одновременных Kinopub Celery-задачах в `docker stats` существует
   не более одного Chromium процесса gateway.
2. В Kinopub нет рабочих импортов `undetected_chromedriver` и локальных cookie
   файлов.
3. Две сессии `kinopub-main`/`kinopub-aux` не видят cookies друг друга.
4. После рестарта gateway новая сессия восстанавливает cookies из единого
   vault, а незавершённая старая задача не зависает навсегда.
5. Очередь проверяется через API: постановка возвращает UUID, polling
   показывает переход `queued -> processing -> succeeded/failed`.
6. Тесты Kinopub проходят без Chromium: HTTP-клиент gateway мокируется.
7. Интеграционный smoke-тест в окружении с Chromium проверяет login/2FA,
   навигацию, DOM lookup, JS extraction, сохранение cookies и закрытие.
