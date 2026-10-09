#!/usr/bin/env python3
"""Rebuild every player's cache from bundled, verified input snapshots."""
from datetime import datetime,timezone
import json
from pathlib import Path
import time
from collections import Counter
from state_labels import add_state_label
from escrow import SNAPSHOT_FIELDS, RULES as ESCROW_RULES
from data_status import data_versions,schedule_coverage,build_update_report,save_update_report,write_json_atomic
from estimate import load,estimate_player,model_fingerprint,VERSION,SEASON,ASSETS,ROOT

def main():
    start=time.perf_counter()
    salaries=load('salaries-2026-27.json');previous=load('salaries-2025-26.json');schedule=load('schedule-2026-27.json')
    target=ASSETS/'net-estimates-2026-27.json'
    old_cache=json.loads(target.read_text(encoding='utf-8')) if target.exists() else None
    estimates=[];scenario_count=0
    for player in salaries['players']:
        default=estimate_player(player,salaries,previous,schedule,full=False)
        current=default['filing_scenario']['status']
        variants={current:default}
        if default['team']!='TOR':
            alternative='mfj' if current=='single' else 'single'
            variants[alternative]=estimate_player(player,salaries,previous,schedule,{'filing_status':alternative},full=False)
        default['filing_scenarios']={status:{k:r[k] for k in (*SNAPSHOT_FIELDS,'contract_baseline')} for status,r in variants.items()}
        default['filing_comparison_note']='US single vs MFJ wage-only counterfactuals exclude unprovided spouse income; not an error/confidence interval. Canadian individual returns are separate.'
        scenario_count+=len(variants);estimates.append(add_state_label(default))
    coverage=schedule_coverage(schedule)
    cache={'cache_schema_version':3,'season':SEASON,'model_version':VERSION,'model_fingerprint':model_fingerprint(),
           'generated_at_utc':datetime.now(timezone.utc).isoformat(),'salary_captured_date':salaries['captured_date'],
           'count':len(estimates),'active_roster_count':sum(x['active_roster'] for x in estimates),
           'profile_count':len(estimates),'marital_evidence_counts':dict(Counter(x['tax_profile']['marital_status'] for x in estimates)),
           'filing_scenario_count':scenario_count,
           'US_players_with_single_and_MFJ':sum(x['team']!='TOR' for x in estimates),
           'Canada_individual_return_players':sum(x['team']=='TOR' for x in estimates),
           'known_regular_season_games':coverage['known_regular_season_games'],
           'unassigned_regular_games':coverage['unassigned_regular_games'],
           'schedule_coverage':coverage,'data_versions':data_versions(ROOT,VERSION),
           'update_report':'assets/update-report-2026-27.json',
           'update_history':'assets/update-history-2026-27.json',
           'settlement_policy':{'default_final_reduction_rate':ESCROW_RULES['default_final_reduction_rate'],
               'default_withholding_rate':ESCROW_RULES['default_withholding_rate'],
               'default_prior_season_final_reduction_rate':ESCROW_RULES['default_prior_season_final_reduction_rate'],
               'current_season_actual_final_reduction_rate':None,
               'default_supplemental_payment_usd':0,
               'basis':ESCROW_RULES['default_rate_basis'],
               'tax_timing_policy':ESCROW_RULES['tax_timing_policy']},
           'precision':'Modeled point estimates; display rounded to USD 10,000; no validated error bound.',
           'estimates':estimates}
    report=build_update_report(old_cache,cache)
    report_path=save_update_report(ASSETS,report)
    write_json_atomic(target,cache)
    print(f'Generated {len(estimates)} estimates in {time.perf_counter()-start:.2f}s: {target}')
    print(f'Changed player records: {report["player_change_count"]}; report: {report_path}')

if __name__=='__main__':main()
