import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'skills/nba-take-home-pay'
sys.path.insert(0,str(ROOT/'scripts'))
from darko_value import snapshot,value_for
from render_chart import display
from import_darko import parse
class DarkoTests(unittest.TestCase):
    def test_complete_unique_source(self):
        data,rows=snapshot()
        self.assertEqual(len(rows),530)
        self.assertEqual(len(data['players']),len(rows))
        self.assertTrue(all(str(n) in rows for n in data['spotrac_to_nba'].values()))
    def test_known_and_missing(self):
        data,rows=snapshot()
        identifier=next(k for k,n in data['spotrac_to_nba'].items() if rows[str(n)]['player_name']=='Nikola Jokic')
        self.assertAlmostEqual(value_for(identifier)['value_usd'],101400179.90969)
        self.assertEqual(value_for('not-an-id')['status'],'unavailable')
        self.assertIsNone(value_for('not-an-id')['value_usd'])
        self.assertEqual(display(None),'暂无估值')
    def test_negative_kept_and_dates_separate(self):
        data,rows=snapshot()
        self.assertTrue(any(r['sal_market_fixed']<0 for r in rows.values() if r['sal_market_fixed'] is not None))
        self.assertEqual(data['ratings_through'],'2026-06-03')
        self.assertNotEqual(data['captured_at'][:10],data['ratings_through'])
    def test_reject_truncated_source(self):
        with self.assertRaises((ValueError,IndexError)):
            parse('players:{keys:["nba_id"],values:[[1]],ratingsThrough:"2026-06-03"')
if __name__=='__main__':unittest.main()
