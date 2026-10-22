"""Valuation parsing, independent enrichment and ranking regression gates."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import fair_salary as f
from take_home import sorted_results

PAGE='players:{keys:["nba_id","player_name","sal_market_fixed","season"],values:[[1,2,3],["Nikola Jokic","Negative Player","Missing Player"],[.99,-.5,null],[2026,2026,2026]]},ratingsThrough:"2026-06-03"'
class FairTests(unittest.TestCase):
 def test_data_only_parser_preserves_negative_and_missing(self):
  s=f.parse_snapshot(PAGE)
  self.assertEqual([p['value_usd'] for p in s['players']],[.99,-.5])
  self.assertEqual(s['ratings_through'],'2026-06-03')
 def test_schema_drift_and_duplicates_fail(self):
  for page in [PAGE.replace('ratingsThrough','other'),PAGE.replace('[1,2,3]','[1,1,3]'),PAGE.replace('sal_market_fixed','renamed')]:
   with self.assertRaises(ValueError):f.parse_snapshot(page)
 def test_name_match_never_uses_spotrac_id_or_changes_taxes(self):
  r={'player':'Nikola Jokić','player_id':'999','estimated_net_usd':123,'spotrac_salary_usd':456}
  original=deepcopy(r);f.enrich(r,f.parse_snapshot(PAGE))
  self.assertEqual(r['fair_salary']['nba_id'],'1')
  self.assertEqual({k:r[k] for k in original},original)
  r={'player':'Unknown'};f.enrich(r,f.parse_snapshot(PAGE))
  self.assertIsNone(r['fair_salary']['value_usd'])
 def test_negative_fair_rank_and_no_fake_zero(self):
  rows=[{'player':n,'player_id':str(i),'fair_salary':{'value_usd':v}} for i,(n,v) in enumerate([('Negative',-5),('Missing',None),('Positive',10)])]
  self.assertEqual([r['player'] for r in sorted_results(rows,'fair')],['Positive','Negative'])
  self.assertEqual([r['player'] for r in sorted_results(rows,'fair','asc')],['Negative','Positive'])
 def test_failed_refresh_leaves_existing_cache(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'cache.json';p.write_text('old')
   with patch('urllib.request.urlopen',side_effect=OSError('offline')):
    with self.assertRaises(OSError):f.refresh(p)
   self.assertEqual(p.read_text(),'old')
 def test_offline_missing_graceful(self):
  with tempfile.TemporaryDirectory() as d:
   self.assertIsNone(f.load_snapshot(str(Path(d)/'none'),True)[0])
if __name__=='__main__':unittest.main()
