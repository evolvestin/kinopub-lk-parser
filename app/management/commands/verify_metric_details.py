import json

from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory

from app.management.base import LoggableBaseCommand
from app.models import SiteMetric
from app.views import get_metric_details


class Command(LoggableBaseCommand):
    help = 'Verifies every non-empty metric variant against its paginated API and admin list.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--only',
            help='Comma-separated metric keys to verify; defaults to every non-empty variant.',
        )

    def handle(self, *args, **options):
        snapshot = SiteMetric.objects.filter(key='global_snapshot').order_by('-created_at').first()
        staff_user = get_user_model().objects.filter(is_staff=True).first()
        if not snapshot or not staff_user:
            raise RuntimeError('A global metric snapshot and a staff user are required')

        client = Client()
        client.force_login(staff_user)
        factory = RequestFactory()
        failures = []
        checked = 0
        only = {key.strip() for key in (options.get('only') or '').split(',') if key.strip()}

        for key, period_data in snapshot.data.items():
            if only and key not in only:
                continue
            entries = period_data if isinstance(period_data, list) else []
            for entry in entries:
                expected = entry.get('collisions', entry.get('value', 0))
                if not expected:
                    continue
                metric_type = entry.get('name') or entry.get('type')
                request = factory.get(
                    f'/api/metrics/details/{key}/',
                    {'type': metric_type, 'offset': 0, 'limit': 1},
                )
                request.user = staff_user
                response = get_metric_details(request, key)
                checked += 1

                if response.status_code != 200:
                    failures.append(f'{key}={metric_type}: API HTTP {response.status_code}')
                    continue

                payload = json.loads(response.content)
                items = payload.get('items', [])
                if not items and not payload.get('is_summary'):
                    failures.append(f'{key}={metric_type}: API returned no first item')

                admin_url = payload.get('admin_url')
                if not admin_url:
                    failures.append(f'{key}={metric_type}: missing admin_url')
                    continue

                admin_response = client.get(admin_url)
                if admin_response.status_code != 200:
                    failures.append(
                        f'{key}={metric_type}: admin HTTP {admin_response.status_code} ({admin_url})'
                    )
                    continue

                context = getattr(admin_response, 'context_data', None)
                if context is None:
                    context = getattr(admin_response, 'context', None)
                changelist = context.get('cl') if context is not None else None
                if changelist is None:
                    failures.append(f'{key}={metric_type}: admin changelist context missing')
                    continue
                actual = changelist.result_count
                if actual != expected:
                    failures.append(
                        f'{key}={metric_type}: expected {expected}, admin has {actual} ({admin_url})'
                    )
                else:
                    self.stdout.write(f'OK {key}={metric_type}: {actual}')

        self.stdout.write(f'Checked variants: {checked}')
        if failures:
            self.stdout.write(self.style.ERROR(f'Failures: {len(failures)}'))
            for failure in failures:
                self.stdout.write(self.style.ERROR(f'  {failure}'))
            raise RuntimeError('Metric detail verification failed')
        self.stdout.write(self.style.SUCCESS('All metric detail variants passed.'))
