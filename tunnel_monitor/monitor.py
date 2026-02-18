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


def extract_url(log_line):
    match = re.search(r'(https://[a-zA-Z0-9-]+\.trycloudflare\.com)', log_line)
    return match.group(1) if match else None


def wait_for_bot_api():
    ping_url = f'http://{BOT_API_HOST}:{BOT_API_PORT}/api/get_me'
    print(f'Waiting for Bot API readiness at {ping_url}...', flush=True)
    while True:
        try:
            resp = requests.get(ping_url, timeout=2)
            if resp.status_code == 200:
                print('Bot API is ready.', flush=True)
                return True
        except requests.RequestException:
            pass
        time.sleep(2)


def send_to_bot(url):
    try:
        headers = {'X-Bot-Token': BOT_TOKEN}
        resp = requests.post(BOT_API_URL, json={'url': url}, headers=headers, timeout=5)
        if resp.status_code == 200:
            print(f'Successfully updated bot URL: {url}', flush=True)
            return True
        else:
            print(f'Bot returned error {resp.status_code}: {resp.text}', flush=True)
    except Exception as e:
        print(f'Failed to connect to bot: {e}', flush=True)
    return False


def main():
    print('Starting Tunnel Monitor...', flush=True)

    while True:
        try:
            client = docker.from_env()
            client.ping()
            break
        except Exception:
            print('Waiting for Docker socket...', flush=True)
            time.sleep(5)

    wait_for_bot_api()

    last_url = None
    container = None

    while True:
        try:
            if not container:
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
                if container:
                    print(f'Attached to target container: {container.name}', flush=True)

                    existing_logs = container.logs(tail=100).decode('utf-8', errors='ignore')
                    found_urls = []
                    for line in existing_logs.split('\n'):
                        url = extract_url(line)
                        if url:
                            found_urls.append(url)

                    if found_urls:
                        last_url = found_urls[-1]
                        print(f'Found latest URL in history: {last_url}. Syncing...', flush=True)
                        send_to_bot(last_url)

                    for line in container.logs(stream=True, tail=0):
                        line_str = line.decode('utf-8', errors='ignore')
                        url = extract_url(line_str)
                        if url and url != last_url:
                            print(f'Detected new URL: {url}', flush=True)
                            last_url = url
                            send_to_bot(url)
                else:
                    time.sleep(POLL_INTERVAL)
            else:
                container.reload()
                if container.status != 'running':
                    print('Tunnel container stopped.', flush=True)
                    container = None
                else:
                    if last_url:
                        send_to_bot(last_url)
                    time.sleep(30)

        except (docker.errors.NotFound, Exception) as e:
            print(f'Connection lost or error: {e}', flush=True)
            container = None
            time.sleep(POLL_INTERVAL)


if __name__ == '__main__':
    main()
