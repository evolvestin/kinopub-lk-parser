import os
import sys
import time

heartbeat_file = os.getenv('HEARTBEAT_FILE', '/tmp/kinopub-parser_heartbeat')
threshold = 60

try:
    stat = os.stat(heartbeat_file)
    age = time.time() - stat.st_mtime
    if age <= threshold:
        sys.exit(0)
    else:
        print(f'Heartbeat stale: {age:.1f}s > {threshold}s (file: {heartbeat_file})')
        sys.exit(1)
except FileNotFoundError:
    print(f'Heartbeat not found (file: {heartbeat_file})')
    sys.exit(1)
except Exception as e:
    print(f'Healthcheck error: {e}')
    sys.exit(1)
