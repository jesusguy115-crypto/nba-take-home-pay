"""Global ranks must not become subset positions after filtering or metric switches."""
import unittest
from take_home import league_rank_metadata
from fair_salary import enrich
class RankScopeTests(unittest.TestCase):
 def test_league_population_not_current_subset(self):
  rows=[{'player_id':str(i),'spotrac_salary_usd':100-i,'estimated_net_usd':n,'filing_scenario':{'status':'single'}} for i,n in enumerate([1,3,2])]
  r=dict(rows[0]);league_rank_metadata(r,rows)
  self.assertEqual(r['league_ranks']['gross'],1)
  self.assertEqual(r['league_ranks']['net'],3)
  r['estimated_net_usd']=50;league_rank_metadata(r,rows)
  self.assertIsNone(r['league_ranks']['net'])
 def test_fair_rank_includes_players_outside_salary_query(self):
  snapshot={'players':[{'name':'Curry','nba_id':'1','value_usd':10},{'name':'Other','nba_id':'2','value_usd':30},{'name':'Unmatched','nba_id':'3','value_usd':20}]}
  r={'player':'Curry'};enrich(r,snapshot)
  self.assertEqual(r['fair_salary']['global_rank'],3)
  self.assertEqual(r['fair_salary']['rank_population'],3)
if __name__=='__main__':unittest.main()
