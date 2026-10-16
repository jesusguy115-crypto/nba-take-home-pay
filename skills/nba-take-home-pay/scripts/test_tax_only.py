"""Regression gates for removal of league adjustments and valuation data."""
import json,unittest
from pathlib import Path
from estimate import estimate_player,load
from story_pack import bridge
ROOT=Path(__file__).resolve().parents[1]
class TaxOnlyTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.cache=load('net-estimates-2026-27.json')
 def test_every_player_and_filing_uses_whole_salary(self):
  for r in self.cache['estimates']:
   for v in [r,*r['filing_scenarios'].values()]:
    self.assertAlmostEqual(v['gross_usd'],r['spotrac_salary_usd']+r.get('extra_cup_bonus_usd',0),places=2)
    self.assertAlmostEqual(v['gross_usd']-v['estimated_tax_usd'],v['estimated_net_usd'],places=2)
    self.assertAlmostEqual(sum(v['components_usd'].values()),v['estimated_tax_usd'],delta=.25)
    self.assertFalse({'escrow_scenario','contract_baseline','cashflow_scenario','darko_value'}&set(v))
 def test_prior_wages_are_not_reduced(self):
  r=next(r for r in self.cache['estimates'] if r['player']=='Stephen Curry')
  annual=next(y for y in r['years'] if y['year']==2026)['annualized_gross']
  self.assertAlmostEqual(annual,r['previous_season_gross_usd']*5/6+r['spotrac_salary_usd']/6,places=2)
 def test_legacy_adjustment_cannot_change_income(self):
  salaries=load('salaries-2026-27.json')
  for scenario in [{'final_reduction_rate':.0548},{'prior_season_final_reduction_rate':.0548},{'escrow_rate':.1}]:
   with self.assertRaises(ValueError):estimate_player(salaries['players'][0],salaries,load('salaries-2025-26.json'),load('schedule-2026-27.json'),scenario)
 def test_video_bridge_explains_only_wages_and_taxes(self):
  for r in self.cache['estimates']:
   steps=bridge(r)
   self.assertFalse(any('联盟' in x['label'] or 'DARKO' in x['label'] for x in steps))
   self.assertAlmostEqual(sum(x['amount'] for x in steps),r['estimated_net_usd'],places=2)
if __name__=='__main__':unittest.main()
