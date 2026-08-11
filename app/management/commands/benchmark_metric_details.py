import json
import time

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext

from app.management.base import LoggableBaseCommand
from app.views import get_metric_details


class Command(LoggableBaseCommand):
    help = 'Benchmarks paginated metric-detail API pages, including SQL count and payload size.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--case',
            action='append',
            metavar='KEY=TYPE',
            help=(
                'Metric case to benchmark. May be repeated; defaults to representative heavy cases.'
            ),
        )
        parser.add_argument(
            '--offsets',
            default='0,50',
            help='Comma-separated offsets to benchmark for every case (default: 0,50).',
        )
        parser.add_argument('--limit', type=int, default=50, help='Page size (1-100).')
        parser.add_argument(
            '--show-sql', action='store_true', help='Print SQL statements for each benchmark case.'
        )

    def handle(self, *args, **options):
        cases = options['case'] or [
            'missing_plot=Movie',
            'missing_kp=Movie',
            'duplicate_photo_urls=TMDB',
        ]
        parsed_cases = []
        for raw_case in cases:
            try:
                key, metric_type = raw_case.split('=', 1)
            except ValueError as exc:
                raise ValueError(f'Invalid --case {raw_case!r}; expected KEY=TYPE') from exc
            parsed_cases.append((key, metric_type))

        offsets = [
            max(0, int(value.strip())) for value in options['offsets'].split(',') if value.strip()
        ]
        limit = min(100, max(1, options['limit']))
        staff_user = get_user_model().objects.filter(is_staff=True).first()
        if not staff_user:
            raise RuntimeError('No staff user exists for API benchmark')

        factory = RequestFactory()
        self.stdout.write(f'Metric detail benchmark: limit={limit}, offsets={offsets}')
        self.stdout.write(
            'case                         offset  elapsed_ms  sql  bytes  items  more'
        )

        for key, metric_type in parsed_cases:
            for offset in offsets:
                request = factory.get(
                    f'/api/metrics/details/{key}/',
                    {'type': metric_type, 'offset': offset, 'limit': limit},
                )
                request.user = staff_user

                start = time.perf_counter()
                with CaptureQueriesContext(connection) as queries:
                    response = get_metric_details(request, key)
                elapsed_ms = (time.perf_counter() - start) * 1000

                if response.status_code != 200:
                    self.stdout.write(
                        self.style.ERROR(
                            f'{key:<28} {offset:>6}  HTTP {response.status_code}: '
                            f'{response.content.decode(errors="replace")[:160]}'
                        )
                    )
                    continue

                payload = json.loads(response.content)
                items = payload.get('items', [])
                self.stdout.write(
                    f'{key:<28} {offset:>6}  {elapsed_ms:>10.2f}  '
                    f'{len(queries):>3}  {len(response.content):>5}  '
                    f'{len(items):>5}  {str(bool(payload.get("has_more"))):>4}'
                )
                if options['show_sql']:
                    for query in queries:
                        self.stdout.write(f'  SQL: {query["sql"]}')
