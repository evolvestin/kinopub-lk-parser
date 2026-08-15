# ТЗ: перенос браузера Kinopub в AssetHub Browser Gateway

## Цель

Убрать запуск Chromium из Kinopub и исключить параллельные Selenium-процессы
на сервере. Все браузерные операции Kinopub выполняются единственным
`browser-gateway` worker внутри AssetHub.

Глобальная Redis-блокировка Kinopub (`kinopub_parser_global_lock`) при этом
остаётся на уровне Celery-задач. Она не ограничивает очередь AssetHub и не
управляет Chromium; она не даёт нескольким Kinopub-парсерам одновременно
отправлять команды для общих профилей и пересекаться с резервным копированием.

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

## Поведение при перегруженной очереди

Каждая browser-команда получает `task_id`, после чего Kinopub ожидает её
завершения polling-запросами. Статус `queued` сам по себе не считается
ошибкой. Если отдельная команда не завершилась за
`BROWSER_GATEWAY_TASK_TIMEOUT_SECONDS` (по умолчанию 900 секунд), клиент
выбрасывает timeout, а парсер обрабатывает это как ошибку браузерной сессии.

Глобальный lock не даёт одной Kinopub-задаче породить несколько параллельных
парсеров: новая задача либо пропускается, либо админская команда получает
ошибку занятости. Очереди обновления деталей и длительностей при пропуске
`process_queues_task` сохраняются в Redis и будут обработаны следующим
запуском. Перегрузка со стороны других проектов в AssetHub всё равно может
увеличить время ожидания и привести к timeout; сам Kinopub пока не имеет
отдельного механизма приоритета. При локальном timeout клиент отправляет
`DELETE` для отмены queued-задачи; уже выполняемая команда получает
`cancel_requested` и завершается worker-ом после текущей операции.
