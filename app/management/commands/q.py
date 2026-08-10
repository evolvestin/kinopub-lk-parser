# ruff: noqa
import time

from app.management.base import LoggableBaseCommand
from app.services.metrics import (
    calculate_duplicate_photo_urls_metric,
    calculate_en_professions_stats_metric,
    calculate_has_imdb_metric,
    calculate_has_kp_metric,
    calculate_missing_country_meta_metric,
    calculate_missing_durations_metric,
    calculate_missing_imdb_id_metric,
    calculate_missing_imdb_metric,
    calculate_missing_kp_metric,
    calculate_missing_plot_metric,
    calculate_missing_status_metric,
    calculate_missing_tmdb_id_metric,
    calculate_missing_year_metric,
    calculate_no_countries_metric,
    calculate_no_genres_metric,
    calculate_persons_avatar_stats_metric,
    calculate_professions_stats_metric,
    calculate_title_collision_metric,
    calculate_tmdb_missing_durations_metric,
    calculate_tmdb_missing_plot_metric,
    calculate_tmdb_missing_status_metric,
    calculate_tmdb_missing_year_metric,
    calculate_tmdb_no_countries_metric,
    calculate_tmdb_no_genres_metric,
    calculate_tmdb_no_kp_metric,
    calculate_tmdb_only_shows_metric,
    calculate_total_countries_metric,
    calculate_total_genres_metric,
    calculate_total_persons_by_show_type_metric,
    calculate_total_shows_metric,
    calculate_unmapped_genres_metric,
    calculate_unused_persons_metric,
    generate_global_metrics_snapshot,
)


class Command(LoggableBaseCommand):
    help = 'Benchmarks execution time for global metrics snapshot and individual metric functions.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--repeat-snapshot',
            action='store_true',
            help='Run generate_global_metrics_snapshot() again instead of reusing benchmark results.',
        )

    def handle(self, *args, **options):
        command_start = time.perf_counter()
        metric_funcs = [
            ('missing_kp', calculate_missing_kp_metric),
            ('missing_imdb', calculate_missing_imdb_metric),
            ('missing_imdb_id', calculate_missing_imdb_id_metric),
            ('tmdb_only_shows', calculate_tmdb_only_shows_metric),
            ('missing_tmdb_id', calculate_missing_tmdb_id_metric),
            ('tmdb_no_kp', calculate_tmdb_no_kp_metric),
            ('has_kp', calculate_has_kp_metric),
            ('has_imdb', calculate_has_imdb_metric),
            ('total_shows', calculate_total_shows_metric),
            ('title_collision', calculate_title_collision_metric),
            ('missing_year', calculate_missing_year_metric),
            ('missing_status', calculate_missing_status_metric),
            ('missing_plot', calculate_missing_plot_metric),
            ('missing_durations', calculate_missing_durations_metric),
            ('no_genres', calculate_no_genres_metric),
            ('total_genres', calculate_total_genres_metric),
            ('unmapped_genres', calculate_unmapped_genres_metric),
            ('no_countries', calculate_no_countries_metric),
            ('missing_country_meta', calculate_missing_country_meta_metric),
            ('total_countries', calculate_total_countries_metric),
            ('total_persons_by_show_type', calculate_total_persons_by_show_type_metric),
            ('persons_avatar_stats', calculate_persons_avatar_stats_metric),
            ('professions_stats', calculate_professions_stats_metric),
            ('en_professions_stats', calculate_en_professions_stats_metric),
            ('duplicate_photo_urls', calculate_duplicate_photo_urls_metric),
            ('unused_persons', calculate_unused_persons_metric),
            ('tmdb_missing_year', calculate_tmdb_missing_year_metric),
            ('tmdb_missing_status', calculate_tmdb_missing_status_metric),
            ('tmdb_missing_plot', calculate_tmdb_missing_plot_metric),
            ('tmdb_missing_durations', calculate_tmdb_missing_durations_metric),
            ('tmdb_no_genres', calculate_tmdb_no_genres_metric),
            ('tmdb_no_countries', calculate_tmdb_no_countries_metric),
        ]

        self.stdout.write('Starting benchmark of metric calculations...\n')
        results = []
        measured_values = {}

        for name, func in metric_funcs:
            start_time = time.perf_counter()
            measured_values[name] = func()
            elapsed = (time.perf_counter() - start_time) * 1000
            results.append((name, elapsed))

        results.sort(key=lambda item: item[1], reverse=True)

        self.stdout.write('=== METRIC BENCHMARK RESULTS (Slowest to Fastest) ===')
        for name, elapsed in results:
            self.stdout.write(f'{name:<30} {elapsed:>8.2f} ms')

        if options['repeat_snapshot']:
            start_snapshot = time.perf_counter()
            generate_global_metrics_snapshot(
                profession_stats=(
                    measured_values.get('professions_stats'),
                    measured_values.get('en_professions_stats'),
                )
            )
            total_snapshot_time = (time.perf_counter() - start_snapshot) * 1000
            snapshot_label = 'TOTAL generate_global_metrics_snapshot():'
        else:
            total_snapshot_time = sum(elapsed for _, elapsed in results)
            snapshot_label = 'TOTAL snapshot (reused benchmark results):'

        self.stdout.write('=====================================================')
        self.stdout.write(f'{snapshot_label:<43} {total_snapshot_time:>8.2f} ms')
        command_total = (time.perf_counter() - command_start) * 1000
        self.stdout.write(f'TOTAL command wall-clock:                 {command_total:>8.2f} ms')
