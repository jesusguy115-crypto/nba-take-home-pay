import unittest,json
from copy import deepcopy
from pathlib import Path
from result_quality import check
from player_context import enrich
class QualityTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.rows=json.loads((Path(__file__).resolve().parents[1]/'assets/net-estimates-2026-27.json').read_text())['estimates']
 def test_all_default_rows(self):
  for r in self.rows:self.assertTrue(check(enrich(deepcopy(r)))['money_reconciled'])
 def test_reject_corrupt_net_tax_and_nan(self):
  for field,value in [('estimated_net_usd',0),('estimated_tax_usd',0),('gross_usd',float('nan'))]:
   r=deepcopy(self.rows[0]);r[field]=value
   with self.assertRaises(ValueError):check(r)
 def test_contract_conflict_is_not_a_combined_contract(self):
  r=enrich(deepcopy(next(r for r in self.rows if r['player']=='James Harden')))
  self.assertEqual(r['contract_context']['status'],'conflict')
  self.assertNotIn('9,654',r['contract_context']['current_summary'])
  self.assertTrue(check(r)['warnings'])
if __name__=='__main__':unittest.main()
