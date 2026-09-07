# Agent operational notes

## KinoPub session end-to-end smoke test

The project has a safe, repeatable check for the HTTP history session:

1. The first process uses the production code endpoint to obtain the fresh
   2FA code, authenticates against the configured KinoPub site, opens the
   history page, and persists the session in a dedicated local vault.
2. A second independent process reuses that vault, opens the history page,
   and must not request another 2FA code.

The production code endpoint is:

```text
https://kinopub.webredirect.org/api/internal/kinopub-code/
```

The endpoint accepts an optional `after=<ISO-8601 timestamp>` query parameter;
use it to exclude codes that existed before the current login challenge.

The token is read from `KINOPUB_CODE_API_TOKEN`; never print it or the code.
The smoke test keeps its cookie file in `/data/kinopub-http-e2e` and must not
delete the normal `/data/kinopub-http-sessions` vault.

Run from the repository root after the local stack is up:

```bash
docker compose exec -T web python scripts/e2e_kinopub_session_smoke.py first --session-dir /data/kinopub-http-e2e
docker compose restart web
docker compose exec -T web python scripts/e2e_kinopub_session_smoke.py second --session-dir /data/kinopub-http-e2e
```

The first phase is allowed to request one real 2FA code. Polling starts only
after the local HTTP driver reaches the 2FA form, accepts a PROD code whose
source timestamp is within the login window, and imports at most one code.
This matters because the endpoint is global and the production scheduler may
issue a code for a different login. The second phase is not allowed to log in
and fails fast if the persisted session is missing or invalid. Use this only
when the user explicitly authorizes a real PROD credential/code check.

The PROD endpoint is backed by the PROD email-listener/database. A local
DEBUG stack with its email listener disabled does not populate that endpoint;
the first phase must therefore run while PROD is actively receiving the mail,
or after a fresh code is visible through the endpoint. A `404` response means
there is no eligible fresh PROD code and is not an HTTP login failure.

After deploying changes to PROD, recreate the web and worker services rather
than relying on an unchanged container, then verify `docker compose ps` before
running the smoke test. The web healthcheck intentionally uses `/robots.txt`,
not `/admin/login/`, so admin rendering cannot block dependent services.

For an HTTP history session, an empty KinoPub document is a recoverable stale
session signal: reload the same URL once, wait for the full response, and let
the resulting `/user/login` redirect enter the normal re-authentication path.
Do not classify that empty response as an invalid OTP or request a resend.

HTTP authentication is serialized with a Redis lock across Celery processes.
If HTTP 2FA times out, do not start the browser fallback: that would create a
second login challenge and spam the Telegram channel. Inspect whether the
email-listener stored a fresh `Code` and whether the PROD endpoint has a fresh
value before retrying.
