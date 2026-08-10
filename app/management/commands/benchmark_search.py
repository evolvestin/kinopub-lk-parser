import json
import statistics
import time

from django.core.management.base import BaseCommand
from django.db.models import Q

from app.models import Person, Show


class Command(BaseCommand):
    help = 'Benchmark title/person search queries and print timings and query plans.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--query',
            action='append',
            dest='queries',
            help='Search term. Can be supplied more than once.',
        )
        parser.add_argument('--repeat', type=int, default=5, help='Measured runs per scenario.')
        parser.add_argument('--warmup', type=int, default=1, help='Warmup runs per scenario.')
        parser.add_argument('--limit', type=int, default=30, help='Webapp result page size.')
        parser.add_argument('--offset', type=int, default=0, help='Webapp result offset.')
        parser.add_argument(
            '--no-explain',
            action='store_true',
            help='Skip EXPLAIN ANALYZE output after timings.',
        )

    def handle(self, *args, **options):
        queries = options['queries'] or ['matrix', 'дюна', 'zzzz-no-match']
        repeat = max(1, options['repeat'])
        warmup = max(0, options['warmup'])
        limit = max(1, options['limit'])
        offset = max(0, options['offset'])

        self.stdout.write(
            f'Search benchmark: repeat={repeat}, warmup={warmup}, limit={limit}, offset={offset}'
        )

        for query in queries:
            self.stdout.write(f'\n=== query: {query!r} ===')
            scenarios = self._scenarios(query, limit, offset)
            for name, scenario in scenarios.items():
                factory = scenario['run']
                for _ in range(warmup):
                    factory()

                timings = []
                rows = None
                for _ in range(repeat):
                    started = time.perf_counter()
                    rows = factory()
                    timings.append((time.perf_counter() - started) * 1000)

                self.stdout.write(
                    f'{name:16} rows={rows!s:>5} '
                    f'min={min(timings):8.2f} ms '
                    f'p50={statistics.median(timings):8.2f} ms '
                    f'p95={self._percentile(timings, 0.95):8.2f} ms '
                    f'max={max(timings):8.2f} ms'
                )

                if not options['no_explain']:
                    self._write_plan(name, scenario['queryset']())

    @staticmethod
    def _percentile(values, percentile):
        if len(values) == 1:
            return values[0]
        return statistics.quantiles(values, n=100, method='inclusive')[int(percentile * 100) - 1]

    @staticmethod
    def _show_search(query):
        return Show.objects.filter(Q(title__icontains=query) | Q(original_title__icontains=query))

    @classmethod
    def _admin_show_search(cls, query):
        return Show.objects.filter(
            Q(title__icontains=query)
            | Q(original_title__icontains=query)
            | Q(plot__icontains=query)
        )

    @classmethod
    def _scenarios(cls, query, limit, offset):
        def webapp_shows_queryset():
            return (
                cls._show_search(query)
                .order_by('-year', '-id')
                .values_list('id', flat=True)[offset : offset + limit]
            )

        def webapp_shows():
            return len(list(webapp_shows_queryset()))

        def webapp_persons_queryset():
            return (
                Person.objects.filter(Q(name__icontains=query) | Q(en_name__icontains=query))
                .order_by('-updated_at')
                .values_list('id', flat=True)[:20]
            )

        def webapp_persons():
            return len(list(webapp_persons_queryset()))

        def bot_shows_queryset():
            return cls._show_search(query).values_list('id', flat=True)[:20]

        def bot_shows():
            return len(list(bot_shows_queryset()))

        def admin_shows_queryset():
            return cls._admin_show_search(query).values_list('id', flat=True)[:100]

        def admin_shows():
            queryset = cls._admin_show_search(query)
            result_count = queryset.count()
            page_count = len(list(admin_shows_queryset()))
            return f'{page_count}/{result_count}'

        return {
            'webapp_shows': {'run': webapp_shows, 'queryset': webapp_shows_queryset},
            'webapp_persons': {'run': webapp_persons, 'queryset': webapp_persons_queryset},
            'bot_shows': {'run': bot_shows, 'queryset': bot_shows_queryset},
            'admin_shows': {'run': admin_shows, 'queryset': admin_shows_queryset},
        }

    def _write_plan(self, name, queryset):
        explain = json.loads(queryset.explain(analyze=True, buffers=True, format='json'))[0]
        nodes = []
        self._collect_plan_nodes(explain['Plan'], nodes)
        execution_time = explain.get('Execution Time', 0)
        self.stdout.write(f'  plan: {" -> ".join(nodes)}; db_execution={execution_time:.2f} ms')

    @classmethod
    def _collect_plan_nodes(cls, node, nodes):
        nodes.append(node['Node Type'])
        for child in node.get('Plans', []):
            cls._collect_plan_nodes(child, nodes)
