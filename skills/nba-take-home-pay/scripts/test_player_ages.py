"""Age boundaries, complete ranking, and cache-only runtime behavior."""
from contextlib import redirect_stdout, redirect_stderr
from datetime import date
from io import StringIO
import json
import unittest
from unittest.mock import patch

import estimate
import take_home
from player_ages import age_on, filter_by_age, load_birthdates


class AgeTests(unittest.TestCase):
    def test_birthday_and_leap_day(self):
        self.assertEqual(age_on('1996-10-11', date(2026, 10, 10)), 29)
        self.assertEqual(age_on('1996-10-11', date(2026, 10, 11)), 30)
        self.assertEqual(age_on('2000-02-29', date(2026, 2, 28)), 25)
        self.assertEqual(age_on('2000-02-29', date(2026, 3, 1)), 26)
        self.assertIsNone(age_on('2000-02-29', date(1999, 1, 1)))

    def test_inclusive_and_exclusive_bounds(self):
        selected = [({'player_id': str(age), 'player': str(age)}, None) for age in (29, 30, 31)]
        births = {str(age): {'birth_date': str(2026-age) + '-01-01'} for age in (29, 30, 31)}
        self.assertEqual([p['player_id'] for p, _ in filter_by_age(selected, births, date(2026, 10, 10), maximum=30)], ['29', '30'])
        self.assertEqual([p['player_id'] for p, _ in filter_by_age(selected, births, date(2026, 10, 10), under=30)], ['29'])
        self.assertEqual([p['player_id'] for p, _ in filter_by_age(selected, births, date(2026, 10, 10), minimum=30, maximum=30)], ['30'])
        with self.assertRaisesRegex(ValueError, '完整排名'):
            filter_by_age(selected, {}, date(2026, 10, 10), maximum=30)

    def query(self, *args):
        out = StringIO()
        with redirect_stdout(out), redirect_stderr(StringIO()), patch.object(estimate, 'estimate_player', side_effect=AssertionError('must not recalculate')):
            take_home.main([*args, '--brief', '--json'])
        return json.loads(out.getvalue())

    def test_dataset_complete_and_sane(self):
        birthdays = load_birthdates()
        cache = json.loads(take_home.CACHE.read_text())
        self.assertEqual(set(birthdays), {p['player_id'] for p in cache['estimates']})
        for row in birthdays.values():
            self.assertTrue(16 <= age_on(row['birth_date'], date(2026, 10, 10)) <= 50, row)
            self.assertTrue(row['source']['source_url'].startswith('https://'))

    def test_top_ten_filters_full_universe_before_sorting(self):
        data = self.query('--top', '10', '--sort', 'net', '--max-age', '30', '--age-date', '2026-10-10')
        cache = json.loads(take_home.CACHE.read_text())
        births = load_birthdates()
        eligible = [p for p in cache['estimates'] if age_on(births[p['player_id']]['birth_date'], date(2026, 10, 10)) <= 30]
        expected = sorted(eligible, key=lambda p: (-p['estimated_net_usd'], p['player'].casefold(), p['player_id']))[:10]
        self.assertEqual([p['player_id'] for p in data['results']], [p['player_id'] for p in expected])
        self.assertEqual(data['matched_count'], len(eligible))
        self.assertEqual(len(data['results']), 10)
        self.assertTrue(all(p['age'] <= 30 and p['query_path'] == 'precomputed_cache' for p in data['results']))

    def test_under_age_differs_from_inclusive_and_date_changes_birthday(self):
        inclusive = self.query('--max-age', '30', '--age-date', '2026-10-10')
        under = self.query('--under-age', '30', '--age-date', '2026-10-10')
        self.assertGreater(inclusive['matched_count'], under['matched_count'])
        self.assertTrue(all(p['age'] < 30 for p in under['results']))
        before = self.query('布克', '--age-date', '2026-10-29')
        after = self.query('布克', '--age-date', '2026-10-30')
        self.assertEqual((before['age'], after['age']), (29, 30))
        self.assertEqual(before['estimated_net_usd'], after['estimated_net_usd'])

    def test_team_range_baseline_and_empty_results(self):
        data = self.query('--team', 'MIN', '--min-age', '25', '--max-age', '30', '--sort', 'net', '--settlement', 'baseline', '--age-date', '2026-10-10')
        for row in data['results']:
            self.assertTrue(25 <= row['age'] <= 30)
            self.assertEqual(row['team'], 'MIN')
            self.assertEqual(row['estimated_net_usd'], row['contract_baseline']['estimated_net_usd'])
        empty = self.query('--top', '10', '--max-age', '10', '--age-date', '2026-10-10')
        self.assertEqual(empty['returned_count'], 0)

    def test_missing_birthdate_refuses_incomplete_ranking(self):
        with patch.object(take_home, 'load_birthdates', return_value={}):
            with self.assertRaises(SystemExit) as err:
                self.query('--top', '10', '--max-age', '30')
            self.assertEqual(err.exception.code, 2)

    def test_invalid_flags(self):
        for args in [('--max-age', '-1'), ('--birth-year-min', '2010', '--birth-year-max', '2009'),
                     ('--min-age', '31', '--max-age', '30'),
                     ('--min-age', '30', '--under-age', '30'), ('--max-age', '30', '--under-age', '30'),
                     ('--top', '10', '--age-date', '2026-02-30'), ('库里', '--max-age', '30')]:
            with self.subTest(args=args), self.assertRaises(SystemExit) as err:
                self.query(*args)
            self.assertEqual(err.exception.code, 2)

    def test_birth_decade_is_not_an_age_shortcut(self):
        data = self.query('--birth-year-min', '2000', '--birth-year-max', '2009', '--top', '10', '--sort', 'net', '--age-date', '2026-10-10')
        self.assertEqual(len(data['results']), 10)
        self.assertTrue(all('2000-01-01' <= p['birth_date'] <= '2009-12-31' for p in data['results']))
        self.assertEqual(data['results'][0]['player'], 'Evan Mobley')
        self.assertEqual(data['query']['age_filter']['birth_year_min'], 2000)

    def test_coverage_and_default_date(self):
        data = self.query('--coverage', '--age-date', '2026-10-10')
        self.assertEqual(data['ages']['known_age_count'], 520)
        self.assertEqual(self.query('库里')['age_as_of'], date.today().isoformat())


if __name__ == '__main__':
    unittest.main()
