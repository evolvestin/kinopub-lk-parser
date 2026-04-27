import os
import re
import time

import docker
import requests

TARGET_CONTAINER_KEYWORD = 'tunnel'
BOT_API_HOST = os.getenv('BOT_API_HOST', 'telegram-bot')
BOT_API_PORT = os.getenv('BOT_API_PORT', '8081')
BOT_API_URL = f'http://{BOT_API_HOST}:{BOT_API_PORT}/api/internal/set_url'
BOT_TOKEN = os.getenv('BOT_TOKEN')
POLL_INTERVAL = 5
SYNC_INTERVAL = 30


def extract_url(log_data):
    if not log_data:
        return None
    matches = re.findall(r'(https://[a-zA-Z0-9-]+\.trycloudflare\.com)', log_data)
    return matches[-1] if matches else None


def send_to_bot(url):
    try:
        headers = {'X-Bot-Token': BOT_TOKEN}
        resp = requests.post(BOT_API_URL, json={'url': url}, headers=headers, timeout=5)
        if resp.status_code == 200:
            return True
        else:
            print(f'Bot API returned error {resp.status_code}: {resp.text}', flush=True)
    except requests.RequestException:
        # Silence connection errors as bot might be restarting
        pass
    return False


def main():
    print('Starting Tunnel Monitor (Active Sync Mode)...', flush=True)

    client = None
    socket_path = '/var/run/docker.sock'

    while not client:
        try:
            if os.path.exists(socket_path):
                client = docker.DockerClient(base_url=f'unix://{socket_path}')
            else:
                client = docker.from_env()
            client.ping()
        except Exception as e:
            print(f'Waiting for Docker socket ({e})...', flush=True)
            client = None
            time.sleep(5)

    last_url = None
    last_sync_time = 0

    while True:
        try:
            container = next(
                (
                    c
                    for c in client.containers.list()
                    if TARGET_CONTAINER_KEYWORD in c.name
                    and 'monitor' not in c.name
                    and c.status == 'running'
                ),
                None,
            )

            if not container:
                last_url = None
                time.sleep(POLL_INTERVAL)
                continue

            logs = container.logs(tail=200).decode('utf-8', errors='ignore')
            current_url = extract_url(logs)

            if current_url:
                now = time.time()
                # Продвигаем URL в бот если:
                # 1. URL изменился
                # 2. Прошло время SYNC_INTERVAL (на случай рестарта бота)
                if current_url != last_url or (now - last_sync_time) > SYNC_INTERVAL:
                    if send_to_bot(current_url):
                        if current_url != last_url:
                            print(f'Detected and synced new URL: {current_url}', flush=True)
                        last_url = current_url
                        last_sync_time = now

            time.sleep(POLL_INTERVAL)

        except Exception as e:
            print(f'Monitor loop error: {e}', flush=True)
            time.sleep(POLL_INTERVAL)


if __name__ == '__main__':
    main()
