from unittest.mock import Mock, patch

from bs4 import BeautifulSoup
from django.test import SimpleTestCase, TestCase, override_settings
from selenium.common.exceptions import StaleElementReferenceException

from app import history_parser
from app.kinopub_http import KinopubHttpDriver
from app.models import Show


class HistoryDetailsRefreshQueueTests(TestCase):
    def _create_show(self, *, plot, updated_at):
        show = Show.objects.create(
            title='Test show',
            original_title='Test show',
            plot=plot,
        )
        Show.objects.filter(pk=show.pk).update(updated_at=updated_at)
        return show

    def test_history_refreshes_only_missing_or_stale_details(self):
        now = history_parser.timezone.now()
        fresh = self._create_show(plot='Fresh description', updated_at=now)
        stale = self._create_show(
            plot='Old description',
            updated_at=now - history_parser.timedelta(days=15),
        )
        missing = self._create_show(plot='', updated_at=now)

        result = history_parser._get_stale_history_detail_ids(
            [fresh.id, stale.id, missing.id],
            now=now,
        )

        self.assertEqual(set(result), {stale.id, missing.id})

    def test_empty_input_does_not_query_or_enqueue(self):
        self.assertEqual(history_parser._get_stale_history_detail_ids([]), [])


class HistoryParserRecoveryTests(SimpleTestCase):
    @override_settings(ENVIRONMENT='DEV')
    @patch('app.management.commands.runhistoryparser.history_parser.run_parser_session')
    def test_manual_history_parser_requires_explicit_local_flag(self, run_parser_session):
        from app.management.commands.runhistoryparser import Command

        Command().handle(allow_kinopub=True)

        run_parser_session.assert_called_once_with()

    @patch('app.history_parser._update_show_details_once')
    def test_show_update_reacquires_the_whole_page_after_browser_recovery(self, update_once):
        update_once.side_effect = [
            StaleElementReferenceException(
                'browser element reference was invalidated by session recovery'
            ),
            'updated',
        ]
        driver = Mock()

        result = history_parser.update_show_details(
            driver,
            1775,
            force=True,
            session_type='main',
        )

        self.assertEqual(result, 'updated')
        self.assertEqual(update_once.call_count, 2)
        self.assertEqual(update_once.call_args_list[0], update_once.call_args_list[1])

    def test_login_url_comparison_ignores_query_and_trailing_slash(self):
        self.assertTrue(
            history_parser._is_login_url(
                'https://kinopub.example/user/login?returnUrl=%2Fhistory',
                'https://kinopub.example/user/login',
            )
        )

    def test_login_state_reports_visible_two_factor_form(self):
        driver = Mock()
        driver.current_url = 'https://kinopub.example/user/login'

        def find_elements(by, selector):
            if selector == 'login-form-formcode':
                code = Mock()
                code.is_displayed.return_value = True
                return [code]
            return []

        driver.find_elements.side_effect = find_elements

        self.assertEqual(
            history_parser._wait_for_login_state(
                driver,
                'https://kinopub.example/user/login',
                timeout=1,
            ),
            '2fa',
        )

    def test_empty_remote_document_is_detected(self):
        driver = Mock()
        driver.page_source = '<html><head></head><body></body></html>'

        self.assertTrue(history_parser.is_empty_browser_page(driver))

    @patch('app.history_parser.logging.warning')
    def test_empty_relation_parse_does_not_clear_existing_values(self, warning):
        details_cell = Mock()
        details_cell.find_elements.return_value = []
        relation = Mock()

        history_parser._update_related_objects_from_details(
            details_cell,
            history_parser.Country,
            relation,
            12345,
            'Страна',
        )

        relation.set.assert_not_called()
        warning.assert_called_once()

    def test_two_factor_submission_sets_value_and_submits_the_form(self):
        driver = Mock()
        code_input = Mock()
        code_input.get_attribute.return_value = '650665'
        submit_btn = Mock()

        history_parser._submit_two_factor_code(driver, code_input, submit_btn, ' 650665 ')

        code_input.clear.assert_called_once_with()
        code_input.send_keys.assert_called_once_with('650665')
        self.assertEqual(driver.execute_script.call_count, 1)
        self.assertIn('const form =', driver.execute_script.call_args.args[0])
        submit_btn.click.assert_called_once_with()

    def test_two_factor_submission_synchronizes_input_before_click(self):
        driver = Mock()
        code_input = Mock()
        code_input.get_attribute.return_value = None
        submit_btn = Mock()

        history_parser._submit_two_factor_code(driver, code_input, submit_btn, '650665')

        self.assertEqual(driver.execute_script.call_count, 2)
        self.assertIn(
            "dispatchEvent",
            driver.execute_script.call_args_list[0].args[0],
        )
        submit_btn.click.assert_called_once_with()

    def test_resend_uses_js_when_remote_element_click_is_unavailable(self):
        driver = Mock()
        resend_btn = Mock()
        resend_btn.is_displayed.return_value = True
        resend_btn.is_enabled.return_value = False
        driver.find_elements.return_value = [resend_btn]
        driver.execute_script.return_value = {'ok': True, 'method': 'form-submit'}

        self.assertTrue(history_parser._click_resend_code_if_available(driver))
        resend_btn.click.assert_not_called()
        self.assertIn("button.click()", driver.execute_script.call_args.args[0])

    def test_resend_returns_false_when_button_is_disabled(self):
        driver = Mock()
        resend_btn = Mock()
        resend_btn.is_displayed.return_value = True
        resend_btn.is_enabled.return_value = False
        driver.find_elements.return_value = [resend_btn]
        driver.execute_script.return_value = False

        self.assertFalse(history_parser._click_resend_code_if_available(driver))

    @patch('app.history_parser.close_driver')
    @patch('app.history_parser.initialize_driver_session', return_value=None)
    def test_parser_run_fails_when_driver_initialization_fails(self, _initialize, close_driver):
        with self.assertRaisesRegex(RuntimeError, 'Failed to initialize'):
            history_parser.run_parser_session()

        close_driver.assert_called_once_with(None)


class HistoryParserRedesignTests(TestCase):
    def _driver_for_html(self, html):
        driver = object.__new__(KinopubHttpDriver)
        driver._soup = BeautifulSoup(html, 'html.parser')
        return driver

    def test_new_episode_history_cards_keep_date_and_season_episode(self):
        driver = self._driver_for_html(
            '<section data-kp-history-group>'
            '<h2 class="kp-section-title">29 октября 2026</h2>'
            '<div class="kp-episode is-watched">'
            '<a class="kp-episode-thumb" href="/item/view/108010/s1e9">'
            'Сезон 1. Эпизод 9</a>'
            '<a class="kp-episode-meta" href="/item/view/108010/s1e9">'
            '<span class="kp-episode-title">Питт</span>'
            '<span class="kp-episode-sub">The Pitt</span></a>'
            '</div></section>'
        )

        with (
            patch('app.history_parser._get_stale_history_detail_ids', return_value=[]),
            patch('app.history_parser.enqueue_show_update'),
            patch('app.history_parser.view_history_created.send'),
            patch('app.history_parser.get_season_durations_and_save'),
        ):
            views_added, stop_parsing = history_parser.parse_and_save_history(
                driver, 'episodes'
            )

        view = history_parser.ViewHistory.objects.get()
        show = Show.objects.get(pk=view.show_id)
        self.assertEqual((views_added, stop_parsing), (1, False))
        self.assertEqual(view.view_date.isoformat(), '2026-10-29')
        self.assertEqual((view.season_number, view.episode_number), (1, 9))
        self.assertEqual((show.title, show.original_title), ('Питт', 'The Pitt'))

    def test_new_movie_history_rows_keep_date_and_title(self):
        driver = self._driver_for_html(
            '<section data-kp-history-group>'
            '<h2 class="kp-section-title">2 ноября 2026</h2>'
            '<div class="kp-item-rows"><div class="kp-item-row">'
            '<div class="kp-item-row-body"><div class="kp-item-row-title">'
            '<span class="kp-type">Фильм</span>'
            '<span class="kp-item-row-name"><a href="/item/view/6589/YA-budu-ryadom">'
            'Я буду рядом</a></span></div></div></div></div></section>'
        )

        with (
            patch('app.history_parser._get_stale_history_detail_ids', return_value=[]),
            patch('app.history_parser.enqueue_show_update'),
            patch('app.history_parser.view_history_created.send'),
            patch('app.history_parser.get_movie_duration_and_save'),
        ):
            views_added, stop_parsing = history_parser.parse_and_save_history(
                driver, 'movies'
            )

        view = history_parser.ViewHistory.objects.get()
        show = Show.objects.get(pk=view.show_id)
        self.assertEqual((views_added, stop_parsing), (1, False))
        self.assertEqual(view.view_date.isoformat(), '2026-11-02')
        self.assertEqual((view.season_number, view.episode_number), (0, 0))
        self.assertEqual((show.title, show.original_title), ('Я буду рядом', 'Я буду рядом'))

    @override_settings(SITE_URL='https://kinopub.test/')
    def test_new_item_details_layout_updates_metadata_and_plot(self):
        driver = self._driver_for_html(
            '<main><div class="kp-head-titles"><h1>Путешествие на поезде!</h1>'
            '<div class="kp-head-orig">Tetsuryou! Meet with Tetsudou Musume</div></div>'
            '<dl class="kp-dl">'
            '<dt>Статус</dt><dd>в эфире</dd>'
            '<dt>Год выхода</dt><dd><a href="/serial?years=2026%3B2026">2026</a></dd>'
            '<dt>Страна</dt><dd><a href="/serial?country=7">Япония</a></dd>'
            '<dt>Жанр</dt><dd><a href="/serial?genre=25">Аниме</a></dd>'
            '</dl><div id="kpPlot">Описание нового сериала.</div></main>'
        )
        driver._last_url = 'https://kinopub.test/item/view/128476'
        show = Show.objects.create(
            kinopub_id=128476,
            title='Old title',
            original_title='Old title',
            type='Series',
        )

        with (
            patch('app.history_parser.open_url_safe', return_value=driver),
            patch('app.history_parser.record_kinopub_source'),
            patch('app.history_parser._update_related_objects_from_details'),
        ):
            updated = history_parser.update_show_details(
                driver, 128476, force=True, session_type='main'
            )

        show.refresh_from_db()
        self.assertEqual(updated.pk, show.pk)
        self.assertEqual(show.title, 'Путешествие на поезде!')
        self.assertEqual(show.original_title, 'Tetsuryou! Meet with Tetsudou Musume')
        self.assertEqual(show.year, 2026)
        self.assertEqual(show.type, 'Series')
        self.assertEqual(show.status, 'Ongoing')
        self.assertEqual(show.plot, 'Описание нового сериала.')
