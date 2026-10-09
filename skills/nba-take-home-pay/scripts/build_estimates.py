#!/usr/bin/env python3
"""Rebuild every player's cache from bundled, verified input snapshots."""
from datetime import datetime,timezone
import json
from pathlib import Path
import time
from collections import Counter
from state_labels import add_state_label
from estimate import load,estimate_player,model_fingerprint,VERSION,SEASON,ASSETS

def main():
    start=time.perf_counter()
    salaries=load('salaries-2026-27.json');previous=load('salaries-2025-26.json');schedule=load('schedule-2026-27.json')
    estimates=[];scenario_count=0
    for player in salaries['players']:
        default=estimate_player(player,salaries,previous,schedule,full=False)
        current=default['filing_scenario']['status']
        variants={current:default}
        if default['team']!='TOR':
            alternative='mfj' if current=='single' else 'single'
            variants[alternative]=estimate_player(player,salaries,previous,schedule,{'filing_status':alternative},full=False)
        default['filing_scenarios']={status:{k:r[k] for k in ('estimated_net_usd','rounded_net_usd','estimated_tax_usd','effective_tax_rate','components_usd')} for status,r in variants.items()}
        default['filing_comparison_note']='US single vs MFJ wage-only counterfactuals exclude unprovided spouse income; not an error/confidence interval. Canadian individual returns are separate.'
        scenario_count+=len(variants);estimates.append(add_state_label(default))
    cache={'season':SEASON,'model_version':VERSION,'model_fingerprint':model_fingerprint(),
           'generated_at_utc':datetime.now(timezone.utc).isoformat(),'salary_captured_date':salaries['captured_date'],
           'count':len(estimates),'active_roster_count':sum(x['active_roster'] for x in estimates),
           'profile_count':len(estimates),'marital_evidence_counts':dict(Counter(x['tax_profile']['marital_status'] for x in estimates)),
           'filing_scenario_count':scenario_count,
           'US_players_with_single_and_MFJ':sum(x['team']!='TOR' for x in estimates),
           'Canada_individual_return_players':sum(x['team']=='TOR' for x in estimates),
           'known_regular_season_games':len(schedule['games']),'unassigned_regular_games':30,
           'precision':'Modeled point estimates; display rounded to USD 10,000; no validated error bound.',
           'estimates':estimates}
    target=ASSETS/'net-estimates-2026-27.json'
    temp=target.with_suffix('.tmp');temp.write_text(json.dumps(cache,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8');temp.replace(target)
    print(f'Generated {len(estimates)} estimates in {time.perf_counter()-start:.2f}s: {target}')

if __name__=='__main__':main()
