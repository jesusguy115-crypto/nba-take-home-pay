#!/usr/bin/env python3
"""Settlement identities, recalculated tax bases and cash/filing boundaries."""
import math
import unittest

from estimate import estimate_player, load
from player_names import resolve
import escrow


class EscrowChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = load('salaries-2026-27.json')
        cls.p = load('salaries-2025-26.json')
        cls.g = load('schedule-2026-27.json')

    def result(self, name='库里', scenario=None):
        player = resolve(self.s['players'], name)[0]
        return estimate_player(player, self.s, self.p, self.g, scenario)

    def test_default_is_explicit_historical_assumption(self):
        r = self.result()
        self.assertEqual(r['escrow_scenario']['final_reduction_rate'], .0548)
        self.assertFalse(r['escrow_scenario']['actual_2026_27_rate_known'])
        self.assertIn('not_current_season_forecast', r['escrow_scenario']['selection_reason'])
        self.assertEqual(r['escrow_scenario']['prior_season_final_reduction_rate'], .0548)
        self.assertAlmostEqual(r['gross_usd'], r['spotrac_salary_usd'] * .9452)
        self.assertAlmostEqual(r['previous_season_adjusted_gross_usd'], r['previous_season_gross_usd'] * .9452)

    def test_after_tax_loss_is_reduced_by_recomputed_taxes(self):
        r = self.result()
        baseline = r['contract_baseline']
        impact = r['settlement_impact']
        self.assertGreater(impact['tax_reduction_usd'], 0)
        self.assertGreater(impact['net_reduction_usd'], 0)
        self.assertLess(impact['net_reduction_usd'], impact['gross_reduction_usd'])
        self.assertAlmostEqual(impact['gross_reduction_usd'] - impact['tax_reduction_usd'],
                               impact['net_reduction_usd'], places=2)
        self.assertGreater(baseline['components_usd']['federal_income_tax'], r['components_usd']['federal_income_tax'])
        self.assertGreater(baseline['components_usd']['resident_state_province_tax'], r['components_usd']['resident_state_province_tax'])
        self.assertGreater(baseline['components_usd']['national_employee_payroll'], r['components_usd']['national_employee_payroll'])
        self.assertGreater(baseline['components_usd']['away_state_tax'], r['components_usd']['away_state_tax'])
        self.assertAlmostEqual(r['gross_usd'] - r['estimated_tax_usd'], r['estimated_net_usd'], places=2)

    def test_baseline_holds_prior_assumption_and_filing_constant(self):
        for status in ('single', 'mfj'):
            r = self.result(scenario={'filing_status': status, 'prior_season_final_reduction_rate': .02})
            b = self.result(scenario={'filing_status': status, 'final_reduction_rate': 0,
                                      'prior_season_final_reduction_rate': .02})
            self.assertEqual(r['contract_baseline']['estimated_net_usd'], b['estimated_net_usd'])
            self.assertEqual(r['contract_baseline']['filing_scenario']['status'], status)
            self.assertEqual(r['contract_baseline']['escrow_scenario']['prior_season_final_reduction_rate'], .02)
            self.assertEqual(b['settlement_impact']['net_reduction_usd'], 0)

    def test_zero_to_full_current_reduction_and_cash_reconciliation(self):
        for rate in (0, .0548, .1):
            r = self.result(scenario={'final_reduction_rate': rate})
            c = r['cashflow_scenario']
            self.assertAlmostEqual(c['initial_before_tax_payable_usd'] + c['modeled_refund_before_tax_usd'] -
                                   c['modeled_additional_collection_before_tax_usd'] +
                                   c['supplemental_settlement_payment_before_tax_usd'],
                                   c['settled_before_tax_gross_usd'], places=2)
            self.assertIsNone(c['actual_net_payroll_deposit_usd'])
            self.assertIsNone(c['actual_settlement_payment_date'])
            self.assertNotIn('net_after_assumed_fees_and_escrow_usd', c)

    def test_initial_withholding_does_not_change_final_taxes(self):
        regular = self.result()
        low = self.result(scenario={'withholding_rate': .01})
        legacy = self.result(scenario={'escrow_rate': .01})
        self.assertEqual(regular['estimated_net_usd'], low['estimated_net_usd'])
        self.assertEqual(low['estimated_net_usd'], legacy['estimated_net_usd'])
        self.assertEqual(low['cashflow_scenario'], legacy['cashflow_scenario'])
        self.assertGreater(low['cashflow_scenario']['modeled_additional_collection_before_tax_usd'], 0)
        self.assertEqual(low['cashflow_scenario']['modeled_refund_before_tax_usd'], 0)
        with self.assertRaises(ValueError):
            self.result(scenario={'withholding_rate': .1, 'escrow_rate': .09})

    def test_rate_boundaries_and_nonfinite_amounts_are_rejected(self):
        for key in ('withholding_rate', 'escrow_rate', 'final_reduction_rate', 'prior_season_final_reduction_rate'):
            for value in (-.01, .10001, float('nan'), float('inf'), True):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    self.result(scenario={key: value})
        for value in (-1, float('nan'), float('inf'), True):
            with self.assertRaises(ValueError):
                self.result(scenario={'settlement_bonus_usd': value})

    def test_cup_bonus_is_not_silently_subject_to_contract_reduction(self):
        base = self.result()
        r = self.result(scenario={'cup_bonus_usd': 500000})
        self.assertAlmostEqual(r['gross_usd'] - base['gross_usd'], 500000)
        self.assertEqual(r['cashflow_scenario']['temporary_escrow_usd'], base['cashflow_scenario']['temporary_escrow_usd'])
        self.assertEqual(r['cashflow_scenario']['modeled_final_reduction_usd'], base['cashflow_scenario']['modeled_final_reduction_usd'])
        self.assertGreater(r['estimated_tax_usd'], base['estimated_tax_usd'])

    def test_supplemental_payment_is_taxed_and_not_part_of_withholding(self):
        base = self.result(scenario={'final_reduction_rate': 0})
        r = self.result(scenario={'final_reduction_rate': 0, 'settlement_bonus_usd': 1000000})
        self.assertAlmostEqual(r['gross_usd'] - base['gross_usd'], 1000000)
        self.assertEqual(r['cashflow_scenario']['temporary_escrow_usd'], base['cashflow_scenario']['temporary_escrow_usd'])
        self.assertGreater(r['estimated_tax_usd'], base['estimated_tax_usd'])
        self.assertGreater(r['estimated_net_usd'], base['estimated_net_usd'])
        self.assertLess(r['estimated_net_usd'] - base['estimated_net_usd'], 1000000)
        self.assertEqual(r['contract_baseline']['estimated_net_usd'], base['estimated_net_usd'])
        self.assertEqual(r['contract_baseline']['extra_settlement_bonus_usd'], 0)
        self.assertEqual(r['settlement_impact']['net_gross_adjustment_usd'], 1000000)

    def test_annual_wage_attribution_uses_settled_wages(self):
        r = self.result(scenario={'final_reduction_rate': .1,
                                  'prior_season_final_reduction_rate': .02,
                                  'settlement_bonus_usd': 120000, 'cup_bonus_usd': 50000})
        settled = r['spotrac_salary_usd'] * .9 + 120000
        a, b = r['years']
        self.assertAlmostEqual(a['annualized_gross'], r['previous_season_gross_usd'] * .98 * 5/6 + settled/6 + 50000)
        self.assertAlmostEqual(a['season_payment'], settled/6 + 50000)
        self.assertAlmostEqual(b['annualized_gross'], settled)
        self.assertAlmostEqual(b['season_payment'], settled * 5/6)

    def test_explicit_annual_income_baseline_preserves_other_income(self):
        player = resolve(self.s['players'], '库里')[0]
        salary = player['cash_total_usd']
        r = self.result(scenario={'final_reduction_rate': .1,
                                  'annual_income_2026': salary * .9 / 6,
                                  'annual_income_2027': salary * .9 * 5 / 6})
        self.assertTrue(math.isfinite(r['contract_baseline']['estimated_net_usd']))
        self.assertGreater(r['contract_baseline']['estimated_net_usd'], r['estimated_net_usd'])
        self.assertAlmostEqual(r['years'][0]['season_attribution_fraction'], 1)
        self.assertAlmostEqual(r['years'][1]['season_attribution_fraction'], 1)

    def test_foreign_source_income_and_credits_use_reduced_wages(self):
        player = next(p for p in self.s['players'] if p['teams_in_active_roster_sections'] == ['SAS'])
        a = estimate_player(player, self.s, self.p, self.g, {'final_reduction_rate': 0})
        b = estimate_player(player, self.s, self.p, self.g, {'final_reduction_rate': .1})
        sources_a = {(y['year'], r['country']): r for y in a['years'] for r in y['foreign_ledger']}
        sources_b = {(y['year'], r['country']): r for y in b['years'] for r in y['foreign_ledger']}
        self.assertTrue(sources_a)
        self.assertEqual(set(sources_a), set(sources_b))
        for key in sources_a:
            self.assertAlmostEqual(sources_b[key]['source_income'], sources_a[key]['source_income'] * .9, places=5)
        self.assertLess(b['components_usd']['foreign_income_tax'], a['components_usd']['foreign_income_tax'])
        self.assertGreaterEqual(b['components_usd']['foreign_tax_credit'], a['components_usd']['foreign_tax_credit'])

    def test_canadian_individual_and_nonactive_payments_keep_explicit_scope(self):
        for player in [next(p for p in self.s['players'] if p['teams_in_active_roster_sections'] == ['TOR']),
                       next(p for p in self.s['players'] if not p['teams_in_active_roster_sections'])]:
            r = estimate_player(player, self.s, self.p, self.g)
            self.assertAlmostEqual(r['gross_usd'], r['spotrac_salary_usd'] * .9452)
            self.assertAlmostEqual(r['gross_usd'] - r['estimated_tax_usd'], r['estimated_net_usd'], places=2)
            self.assertEqual(r['contract_baseline']['filing_scenario']['status'], r['filing_scenario']['status'])
            if not r['active_roster']:
                self.assertTrue(any('实际适用扣减' in f for f in r['specific_uncertainties']))


if __name__ == '__main__':
    unittest.main(verbosity=2)
