#!/bin/sh

set -e

echo "Clearing data directory for a clean start..."
find /data/ -mindepth 1 -delete

echo "Attempting to restore database from backup..."
python manage.py restorebackup

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Creating superuser if it doesn't exist..."
python manage.py shell << END
import os
from django.contrib.auth import get_user_model

User = get_user_model()
username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')

if not User.objects.filter(username=username).exists():
    email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
    password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
    if password:
        User.objects.create_superuser(username, email, password)
        print(f"Superuser '{username}' created.")
    else:
        print("DJANGO_SUPERUSER_PASSWORD not set, skipping superuser creation.")
else:
    print(f"Superuser '{username}' already exists.")
END

echo "Starting background services (parser, etc.)..."
python manage.py runservices &

echo "Starting Django development server on 0.0.0.0:8000..."
exec python manage.py runserver 0.0.0.0:8000 --insecure