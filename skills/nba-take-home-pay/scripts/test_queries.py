#!/usr/bin/env python3
"""Query behavior gates: no recalculation, ranking scope, and safe short answers."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import estimate
import take_home


class FastQueryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cache = json.loads(take_home.CACHE.read_text(encoding='utf-8'))
        cls.players = cls.cache['estimates']

    def query(self, *arguments, forbid_compute=True):
        stdout, stderr = StringIO(), StringIO()
        # The query under test still performs its freshness comparison. Source
        # changes made while packaging do not invalidate these behavioral fixtures.
        with patch.object(take_home, 'read', return_value=deepcopy(self.cache)), \
             patch.object(estimate, 'model_fingerprint', return_value=self.cache['model_fingerprint']), \
             redirect_stdout(stdout), redirect_stderr(stderr):
            if forbid_compute:
                with patch.object(estimate, 'estimate_player', side_effect=AssertionError('unexpected tax recomputation')):
                    result = take_home.main(list(arguments))
            else:
                result = take_home.main(list(arguments))
        return result, stdout.getvalue(), stderr.getvalue()

    def json_query(self, *arguments):
        code, output, stderr = self.query(*arguments, '--json')
        self.assertIn(code, (None, 0))
        self.assertEqual(stderr, '')
        return json.loads(output)

    def test_default_and_explicit_filing_use_cache(self):
        row = next(p for p in self.players if p['player'] == 'Stephen Curry')
        default = self.json_query('库里')
        single = self.json_query('库里', '--filing-status', 'single')
        self.assertEqual(default['query_path'], 'precomputed_cache')
        self.assertEqual(default['estimated_net_usd'], row['estimated_net_usd'])
        self.assertEqual(single['estimated_net_usd'], row['filing_scenarios']['single']['estimated_net_usd'])
        self.assertEqual(single['components_usd'], row['filing_scenarios']['single']['components_usd'])
        self.assertEqual(single['filing_scenario']['status'], 'single')
        self.assertEqual(single['filing_scenario']['selection_reason'], 'user_requested_counterfactual')
        self.assertTrue(any('依法可按Single' in value for value in single['specific_uncertainties']))
        self.assertFalse(any('只纳入球员工资' in value for value in single['specific_uncertainties']))

    def test_all_cached_variants_keep_their_metadata_and_original_unchanged(self):
        for row in self.players:
            original = deepcopy(row)
            for status, variant in row['filing_scenarios'].items():
                selected = take_home.cached_scenario(row, status)
                self.assertEqual(selected['filing_scenario']['status'], status)
                self.assertEqual(selected['specific_uncertainties'], variant['specific_uncertainties'])
                for key in take_home.AMOUNT_FIELDS:
                    self.assertEqual(selected[key], variant[key])
            self.assertEqual(row, original)

    def test_gross_and_net_rankings_use_correct_sort_values(self):
        for basis, key in [('gross', 'spotrac_salary_usd'), ('net', 'estimated_net_usd')]:
            actual = self.json_query('--top', '10', '--sort', basis, '--brief')
            expected = sorted(self.players, key=lambda p: (-p[key], p['player'].casefold(), str(p['player_id'])))[:10]
            self.assertEqual([p['player_id'] for p in actual['results']], [p['player_id'] for p in expected])
            self.assertEqual(actual['query']['scope'], 'all')
            self.assertEqual(actual['query']['sort'], basis)
            self.assertEqual(actual['matched_count'], len(self.players))
            self.assertEqual(actual['returned_count'], 10)

    def test_gross_top_with_mfj_does_not_validate_unreturned_toronto_players(self):
        output = self.json_query('--top', '5', '--filing-status', 'mfj', '--brief')
        self.assertEqual(output['matched_count'], len(self.players))
        self.assertEqual(output['returned_count'], 5)
        self.assertTrue(all(row['filing_scenario']['status'] == 'mfj' for row in output['results']))

    def test_net_ranking_uses_unrounded_amount_and_stable_ties(self):
        rows = [dict(player='A', player_id='1', estimated_net_usd=10.01, rounded_net_usd=0),
                dict(player='Z', player_id='2', estimated_net_usd=10.04, rounded_net_usd=0),
                dict(player='B', player_id='3', estimated_net_usd=10.04, rounded_net_usd=0)]
        ordered = take_home.sorted_results(rows, 'net')
        self.assertEqual([p['player'] for p in ordered], ['B', 'Z', 'A'])
        self.assertEqual([p['rank'] for p in ordered], [1, 1, 3])

    def test_team_scope_distinguishes_roster_from_payers(self):
        # Pick a team with an off-roster payer so this detects accidental omissions.
        team = next(team for team in take_home.TEAMS if any(
            team in row['paying_teams'] and (not row['active_roster'] or row['team'] != team)
            for row in self.players))
        roster = self.json_query('--team', team, '--brief')
        payers = self.json_query('--team', team, '--scope', 'all', '--brief')
        self.assertEqual(roster['query']['scope'], 'active')
        self.assertEqual({p['player_id'] for p in roster['results']},
                         {p['player_id'] for p in self.players if p['active_roster'] and p['team'] == team})
        self.assertEqual({p['player_id'] for p in payers['results']},
                         {p['player_id'] for p in self.players if team in p['paying_teams']})
        self.assertIn('全部付款球队的总薪资', payers['query']['scope_note'])
        for row in payers['results']:
            original = next(p for p in self.players if p['player_id'] == row['player_id'])
            self.assertEqual(row['spotrac_salary_usd'], original['spotrac_salary_usd'])

    def test_comparison_preserves_order_deduplicates_and_corrects_team(self):
        output = self.json_query('--compare', '湖人库里', '杜兰特', '库里', '杨瀚森', '--brief')
        self.assertEqual([p['player'] for p in output['results']], ['Stephen Curry', 'Kevin Durant', 'Yang Hansen'])
        self.assertEqual(output['query']['sort'], 'input')
        self.assertEqual(output['returned_count'], 3)
        self.assertIn('team_correction', output['results'][0])
        self.assertTrue(output['results'][1]['team_tax_context']['team_in_no_state_income_tax_state'])
        self.assertIn('免税州', output['results'][1]['team_tax_context']['display_team'])

    def test_ambiguous_batch_fails_with_no_partial_numbers(self):
        code, output, _ = self.query('--compare', '库里', '鲍尔', '--brief', '--json')
        data = json.loads(output)
        self.assertEqual(code, 2)
        self.assertEqual(data['status'], 'query_errors')
        self.assertEqual(data['errors'][0]['status'], 'ambiguous')
        self.assertNotIn('results', data)

    def test_brief_preserves_necessary_caveats_and_is_smaller(self):
        regular = self.json_query('库里')
        short = self.json_query('库里', '--brief')
        self.assertEqual(short['rounded_net_usd'], regular['rounded_net_usd'])
        self.assertEqual(short['specific_uncertainties'], regular['specific_uncertainties'])
        self.assertEqual(short['tax_profile']['marital_status'], regular['tax_profile']['marital_status'])
        self.assertEqual(short['sources']['salary'], regular['sources']['salary'])
        self.assertIn('common_uncertainties', short)
        self.assertEqual(set(short['filing_scenarios']), {'single', 'mfj'})
        self.assertLess(len(json.dumps(short)), len(json.dumps(regular)))
        self.assertNotIn('components_usd', short)
        self.assertNotIn('years', short)

    def test_schedule_note_is_data_driven(self):
        example = {'unassigned_regular_games': 0, 'schedule_coverage': {'unassigned_games_per_team': {'GSW': 0}}}
        self.assertIn('全部缓存', take_home.schedule_note(example, 'GSW'))
        example['schedule_coverage']['unassigned_games_per_team']['GSW'] = 3
        self.assertIn('3场', take_home.schedule_note(example, 'GSW'))
        self.assertNotIn('2场', take_home.schedule_note(example, 'GSW'))

    def test_custom_residence_caveat_matches_used_residence(self):
        note = take_home.common_uncertainties(self.cache, 'GSW', {'country': 'US', 'state': 'TX', 'city': 'Houston'})[0]
        self.assertIn('US TX Houston', note)
        self.assertNotIn('球队城市', note)

    def test_conflicting_operations_are_rejected(self):
        for args in [('库里', '--coverage'), ('--top', '5', '--coverage'), ('库里', '--explain', '--ledger')]:
            with self.assertRaises(SystemExit) as error:
                self.query(*args)
            self.assertEqual(error.exception.code, 2)

    def test_toronto_never_gets_us_filing_status(self):
        toronto = next(p for p in self.players if p['team'] == 'TOR')
        row = self.json_query(toronto['player'], '--filing-status', 'individual_canada', '--brief')
        self.assertEqual(row['filing_scenario']['status'], 'individual_canada')
        with self.assertRaises(SystemExit) as error:
            self.query(toronto['player'], '--filing-status', 'mfj')
        self.assertEqual(error.exception.code, 2)

    def test_fingerprint_gate_rejects_stale_cache(self):
        with patch.object(take_home, 'read', return_value=self.cache), \
             patch.object(estimate, 'model_fingerprint', return_value='stale'), \
             redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit) as error:
                take_home.main(['库里', '--json'])
        self.assertEqual(error.exception.code, 2)

    def test_explain_recomputes_and_preserves_requested_status(self):
        curry = next(p for p in self.players if p['player'] == 'Stephen Curry')
        source = deepcopy(curry)
        source['filing_scenario']['status'] = 'single'
        with patch.object(take_home, 'read', return_value=deepcopy(self.cache)), \
             patch.object(estimate, 'model_fingerprint', return_value=self.cache['model_fingerprint']), \
             patch.object(estimate, 'estimate_player', return_value=source) as calculator, \
             redirect_stdout(StringIO()) as output:
            take_home.main(['库里', '--explain', '--filing-status', 'single'])
        self.assertEqual(calculator.call_count, 1)
        self.assertEqual(calculator.call_args.args[4], {'filing_status': 'single'})
        self.assertTrue(calculator.call_args.kwargs['full'])
        self.assertEqual(json.loads(output.getvalue())['query_path'], 'recomputed_detail_or_scenario')


if __name__ == '__main__':
    unittest.main()
