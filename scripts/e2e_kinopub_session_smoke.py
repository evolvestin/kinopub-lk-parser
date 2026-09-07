"""Verify KinoPub HTTP login, history access, and session reuse across processes."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kinopub_parser.settings')
import django  # noqa: E402
from django.conf import settings  # noqa: E402
from selenium.webdriver.common.by import By  # noqa: E402

django.setup()

from app.kinopub_http import KinopubHttpDriver  # noqa: E402


CODE_ENDPOINT = 'https://kinopub.webredirect.org/api/internal/kinopub-code/'
POLL_INTERVAL_SECONDS = 2
CODE_TIMESTAMP_TOLERANCE_SECONDS = 3
CODE_MAX_DELAY_SECONDS = 60


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('first', 'second'))
    parser.add_argument('--session-dir', default='/data/kinopub-http-e2e')
    parser.add_argument('--code-endpoint', default=CODE_ENDPOINT)
    parser.add_argument('--wait-seconds', type=int, default=240)
    return parser.parse_args()


def _session_file(session_dir: str) -> Path:
    return Path(session_dir) / 'main.json'


def _code_timestamp(payload: dict) -> datetime:
    timestamp = payload.get('created_at') or payload['received_at']
    return datetime.fromisoformat(timestamp.replace('Z', '+00:00'))


def _poll_fresh_codes(endpoint: str, started_at: datetime, timeout: int, stop_event, Code):
    token = settings.KINOPUB_CODE_API_TOKEN
    if not token:
        raise RuntimeError('KINOPUB_CODE_API_TOKEN is not configured')

    deadline = time.monotonic() + timeout
    last_error = None
    seen_timestamps = set()
    imported_count = 0
    while time.monotonic() < deadline and not stop_event.is_set():
        try:
            response = requests.get(
                endpoint,
                headers={'X-Kinopub-Code-Token': token},
                params={'after': started_at.isoformat()},
                timeout=(5, 15),
            )
            if response.status_code == 200:
                payload = response.json()
                received_at = _code_timestamp(payload)
                timestamp_key = received_at.isoformat()
                code_window_start = started_at - timedelta(seconds=CODE_TIMESTAMP_TOLERANCE_SECONDS)
                code_window_end = started_at + timedelta(seconds=CODE_MAX_DELAY_SECONDS)
                if (
                    code_window_start <= received_at <= code_window_end
                    and timestamp_key not in seen_timestamps
                ):
                    code_obj = Code.objects.create(
                        code=payload['code'],
                        telegram_message_id=-1,
                        received_at=received_at,
                        source_uid=f'e2e-prod:{time.time_ns()}:{timestamp_key}',
                    )
                    # Preserve the source timestamp. The HTTP driver uses
                    # Code.created_at as the lower bound for this 2FA
                    # challenge; local insertion time must not make an older
                    # PROD code look fresh.
                    Code.objects.filter(pk=code_obj.pk).update(
                        created_at=max(received_at, started_at),
                    )
                    seen_timestamps.add(timestamp_key)
                    imported_count += 1
                    # A second global endpoint value can belong to a
                    # concurrent PROD login. Never submit it automatically.
                    if imported_count >= 1:
                        return imported_count
            elif response.status_code not in (404,):
                last_error = f'HTTP {response.status_code}'
        except requests.RequestException as exc:
            last_error = str(exc)
        time.sleep(POLL_INTERVAL_SECONDS)

    if stop_event.is_set():
        return imported_count
    raise TimeoutError(
        'Timed out waiting for a fresh PROD KinoPub code'
        + (f' ({last_error})' if last_error else '')
    )


def _history_url() -> str:
    return f'{settings.SITE_URL.rstrip("/")}/history/index/{settings.KINOPUB_LOGIN}'


def _assert_history_session(driver):
    history_url = _history_url()
    driver.get(history_url)
    if '/user/login' in driver.current_url:
        raise RuntimeError(f'History redirected to login: {driver.current_url}')
    if not driver.find_elements(By.CSS_SELECTOR, "a[href*='/user/logout']"):
        raise RuntimeError('History page does not expose an authenticated logout marker')
    if len(driver.page_source) < 200:
        raise RuntimeError('History page is unexpectedly empty')
    return driver.current_url


def _first_phase(args):
    session_dir = Path(args.session_dir)
    session_dir.mkdir(parents=True, exist_ok=True)
    session_file = _session_file(args.session_dir)
    if session_file.exists():
        raise RuntimeError(f'First phase requires a clean dedicated vault: {session_file}')

    # Start polling only after the HTTP driver reaches the actual 2FA form.
    # Polling earlier can pick a code belonging to another concurrent login.
    from app.models import Code

    driver = None
    try:
        import threading

        code_error = []
        stop_event = threading.Event()
        imported_count = []
        auth_error = []

        driver = KinopubHttpDriver(
            base_url=settings.SITE_URL,
            login=settings.KINOPUB_LOGIN,
            password=settings.KINOPUB_PASSWORD,
            profile_key='main',
            timeout=settings.KINOPUB_HTTP_TIMEOUT_SECONDS,
        )

        def authenticate():
            try:
                driver.get(settings.SITE_URL)
                driver.ensure_authenticated()
            except Exception as exc:  # pragma: no cover - exercised by live smoke run
                auth_error.append(exc)

        def import_code():
            try:
                while driver.code_wait_started_at is None and not stop_event.is_set():
                    time.sleep(0.2)
                if driver.code_wait_started_at is None:
                    return
                imported_count.append(
                    _poll_fresh_codes(
                        args.code_endpoint,
                        driver.code_wait_started_at,
                        args.wait_seconds,
                        stop_event,
                        Code,
                    )
                )
            except Exception as exc:  # pragma: no cover - exercised by live smoke run
                code_error.append(exc)

        auth_thread = threading.Thread(target=authenticate, daemon=True)
        code_thread = threading.Thread(target=import_code, daemon=True)
        auth_thread.start()
        code_thread.start()
        try:
            auth_thread.join(timeout=args.wait_seconds + 30)
            if auth_thread.is_alive():
                raise TimeoutError('HTTP authentication thread did not finish')
            if auth_error:
                raise auth_error[0]
            if code_error:
                raise code_error[0]
            if not driver._has_logout_marker():
                raise RuntimeError('HTTP driver did not finish with an authenticated session')
            current_url = _assert_history_session(driver)
            driver.persist_cookies()
            print(
                json.dumps(
                    {
                        'phase': 'first',
                        'history_url': current_url,
                        'session_file': str(session_file),
                        'codes_imported': imported_count[0] if imported_count else 0,
                    }
                )
            )
        finally:
            stop_event.set()
            code_thread.join(timeout=5)
    finally:
        if driver:
            driver.quit()


def _second_phase(args):
    session_file = _session_file(args.session_dir)
    if not session_file.exists():
        raise RuntimeError(f'Persisted session is missing: {session_file}')

    driver = KinopubHttpDriver(
        base_url=settings.SITE_URL,
        login=settings.KINOPUB_LOGIN,
        password=settings.KINOPUB_PASSWORD,
        profile_key='main',
        timeout=settings.KINOPUB_HTTP_TIMEOUT_SECONDS,
    )
    try:
        driver.get(settings.SITE_URL)
        if not driver._has_logout_marker():
            raise RuntimeError('Persisted session was not accepted; refusing to request a new code')
        current_url = _assert_history_session(driver)
        print(json.dumps({'phase': 'second', 'history_url': current_url, 'session_file': str(session_file)}))
    finally:
        driver.quit()


def main():
    args = _parse_args()
    settings.KINOPUB_HTTP_SESSION_DIR = args.session_dir
    if args.phase == 'first':
        _first_phase(args)
    else:
        _second_phase(args)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'KinoPub E2E smoke failed: {exc}', file=sys.stderr)
        raise SystemExit(1)
