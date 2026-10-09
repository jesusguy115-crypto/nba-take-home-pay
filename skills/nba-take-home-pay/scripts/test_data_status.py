"""Regression tests for update evidence and schedule completeness (no tax changes)."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from data_status import (CATEGORY_FILES, build_update_report, data_versions,
                         save_update_report, schedule_coverage, schedule_uncertainty)

ROOT = Path(__file__).resolve().parents[1]


def sample_cache():
    return {
        'season': '2026-27', 'generated_at_utc': '2026-10-10T00:00:00Z',
        'model_fingerprint': 'same', 'data_versions': {
            name: {'sha256': name, 'version': 'sha256:' + name, 'as_of': '2026-10-09'}
            for name in CATEGORY_FILES},
        'schedule_coverage': {'known_regular_season_games': 1200},
        'estimates': [{
            'player_id': 1, 'player': 'Player A', 'team': 'GSW', 'paying_teams': ['GSW'],
            'active_roster': True, 'tax_profile': {'marital_status': 'unknown'},
            'filing_scenario': {'status': 'single'}, 'spotrac_salary_usd': 100,
            'previous_season_gross_usd': 90, 'gross_usd': 100,
            'estimated_net_usd': 50, 'estimated_tax_usd': 50,
            'components_usd': {'federal': 30, 'state': 20},
            'filing_scenarios': {'single': {'estimated_net_usd': 50}, 'mfj': {'estimated_net_usd': 52}},
        }],
    }


class CoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schedule = json.loads((ROOT / 'assets/schedule-2026-27.json').read_text(encoding='utf-8'))

    def test_coverage_recounts_games_not_stale_summaries(self):
        schedule = copy.deepcopy(self.schedule)
        removed = schedule['games'].pop()
        schedule['unassigned_regular_season_games_total'] = 999
        schedule['game_count'] = 999
        result = schedule_coverage(schedule)
        self.assertEqual(result['known_regular_season_games'], 1199)
        self.assertEqual(result['unassigned_regular_games'], 31)
        for team in (removed['home'], removed['away']):
            self.assertEqual(result['unassigned_games_per_team'][team], 3)
            self.assertIn('仍有3场', schedule_uncertainty(schedule, team))
        self.assertEqual(result['published_unassigned_games'], len(schedule['unassigned_games']))
        self.assertEqual(result['additional_games_not_listed'], 25)

    def test_duplicate_games_are_rejected(self):
        schedule = copy.deepcopy(self.schedule)
        schedule['games'].append(schedule['games'][0])
        with self.assertRaisesRegex(ValueError, 'Duplicate assigned'):
            schedule_coverage(schedule)

    def test_complete_team_gets_no_false_missing_warning(self):
        schedule = {'games': [], 'unassigned_games': []}
        for i in range(82):
            schedule['games'].append({'game_id': str(i), 'home': 'GSW', 'away': 'HOU'})
        self.assertIn('均已确定', schedule_uncertainty(schedule, 'GSW'))
        self.assertEqual(schedule_coverage(schedule)['unassigned_games_per_team']['GSW'], 0)


class ProvenanceTests(unittest.TestCase):
    def test_category_versions_change_independently_and_keep_source_date(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for names in CATEGORY_FILES.values():
                for name in names:
                    path = root / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text('{"captured_date":"2026-10-09"}' if name.endswith('.json') else '# engine\n')
            before = data_versions(root, 'v1')
            path = root / 'assets/salaries-2026-27.json'
            path.write_text('{"captured_date":"2026-10-09","new_salary":123}')
            after = data_versions(root, 'v1')
            self.assertNotEqual(before['salary']['sha256'], after['salary']['sha256'])
            for category in ('schedule', 'tax_rules', 'profiles', 'model'):
                self.assertEqual(before[category], after[category])
            self.assertEqual(after['salary']['as_of'], '2026-10-09')

    def test_legacy_comparison_does_not_invent_old_versions(self):
        old, new = sample_cache(), sample_cache()
        del old['data_versions']
        result = build_update_report(old, new)
        self.assertEqual(result['comparison_status'], 'legacy_cache_without_category_versions')
        self.assertEqual(result['player_change_count'], 0)
        self.assertTrue(all(x['status'] == 'previous_version_unknown' for x in result['input_versions'].values()))

    def test_player_delta_has_observed_and_shared_reasons(self):
        old, new = sample_cache(), sample_cache()
        row = new['estimates'][0]
        row.update(spotrac_salary_usd=110, gross_usd=110, estimated_net_usd=55, estimated_tax_usd=55)
        new['data_versions']['salary']['sha256'] = 'new-salary'
        new['data_versions']['schedule']['sha256'] = 'new-schedule'
        result = build_update_report(old, new)['player_changes'][0]
        self.assertIn('salary_changed', result['observed_changes'])
        self.assertEqual(result['amounts']['estimated_net_usd']['delta_usd'], 5)
        self.assertEqual(result['shared_inputs_changed'], ['salary', 'schedule'])

    def test_alternative_only_changes_are_reported(self):
        old, new = sample_cache(), sample_cache()
        new['estimates'][0]['filing_scenarios']['mfj']['estimated_net_usd'] = 53
        result = build_update_report(old, new)['player_changes'][0]
        self.assertEqual(result['amounts']['estimated_net_usd']['delta_usd'], 0)
        self.assertEqual(result['filing_scenario_net_changes']['mfj']['delta_usd'], 1)

    def test_noop_rebuild_does_not_append_history(self):
        old, new = sample_cache(), sample_cache()
        with tempfile.TemporaryDirectory() as td:
            initial = build_update_report(None, old)
            save_update_report(td, initial)
            save_update_report(td, initial)
            save_update_report(td, build_update_report(old, new))
            history = json.loads((Path(td) / 'update-history-2026-27.json').read_text())
            self.assertEqual(len(history['reports']), 1)
            self.assertEqual(json.loads((Path(td) / 'update-report-2026-27.json').read_text())['player_change_count'], 0)

    def test_added_removed_players_have_no_fabricated_deltas(self):
        old, new = sample_cache(), sample_cache()
        new['estimates'][0]['player_id'] = 2
        changes = build_update_report(old, new)['player_changes']
        self.assertEqual(len(changes), 2)
        self.assertEqual(changes[0]['observed_changes'][0], 'player_removed')
        self.assertEqual(changes[1]['observed_changes'][0], 'player_added')
        self.assertTrue(all(row['amounts']['estimated_net_usd']['delta_usd'] is None for row in changes))


if __name__ == '__main__':
    unittest.main()
