import json
from pathlib import Path
import unittest
from story_pack import breakdown
class StoryTests(unittest.TestCase):
    def test_all_cached_default_ledgers_reconcile(self):
        rows=json.loads((Path(__file__).resolve().parents[1]/'assets/net-estimates-2026-27.json').read_text())['estimates']
        for row in rows:
            ledger=breakdown([row])['players'][0]
            self.assertAlmostEqual(sum(s['amount'] for s in ledger['steps']),row['estimated_net_usd'],places=2)
        d=breakdown(rows[:2])['difference']
        self.assertAlmostEqual(sum(s['amount'] for s in d['steps']),d['net_difference'],places=2)
    def test_missing_money_is_rejected(self):
        with self.assertRaises(ValueError):
            breakdown([{'player':'Test','spotrac_salary_usd':100,'estimated_net_usd':10,'cashflow_scenario':{'modeled_final_reduction_usd':0},'components_usd':{}}])
if __name__=='__main__':unittest.main()
