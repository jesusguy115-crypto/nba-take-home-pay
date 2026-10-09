#!/usr/bin/env python3
"""Targeted tax boundaries and full-cache accounting checks, no network."""
import json
import math
from pathlib import Path
import unittest

import tax_federal as federal
import tax_east as east
import tax_west as west
from estimate import load,estimate_player,model_fingerprint,season_foreign_ledgers,player_profiles
from duty_days import make_ledger
from player_names import resolve, requires_clarification

class ModelChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s=load('salaries-2026-27.json');cls.p=load('salaries-2025-26.json');cls.g=load('schedule-2026-27.json')
        cls.cache=load('net-estimates-2026-27.json')

    def player(self,n):return resolve(self.s['players'],n)[0]
    def result(self,n,scenario=None):return estimate_player(self.player(n),self.s,self.p,self.g,scenario)

    def test_us_brackets_and_employee_caps(self):
        r=federal.calculate_us(1_000_000)
        self.assertAlmostEqual(r['federal'],320000.25,places=2)
        self.assertAlmostEqual(r['payroll'],33139,places=2)
        self.assertAlmostEqual(r['social_security'],11439,places=2)
        self.assertTrue(federal.calculate_us(1_000_000,2027)['proxy'])

    def test_joint_household_social_security_is_per_person(self):
        r=federal.calculate_us(400000,filing_status='mfj',spouse_wages=200000)
        self.assertAlmostEqual(r['social_security'],22878,places=2)
        self.assertAlmostEqual(r['additional_medicare'],1350,places=2)
        self.assertAlmostEqual(r['payroll'],30028,places=2)
        self.assertEqual(r['payroll_by_person']['primary']['social_security'],11439)
        single=federal.calculate_us(62587158)
        joint=federal.calculate_us(62587158,filing_status='mfj')
        self.assertAlmostEqual(single['tax']-joint['tax'],40199.75,places=2)

    def test_all_players_have_evidence_and_filing_scenarios(self):
        profiles=player_profiles()
        self.assertEqual(set(profiles),{p['player_id'] for p in self.s['players']})
        for r in self.cache['estimates']:
            profile=r['tax_profile']
            self.assertEqual(profile['actual_filing_status'],'unknown')
            if profile['marital_status']=='married':
                self.assertTrue(profile['evidence'])
                self.assertTrue(profile['source'].startswith('https://'))
            if r['team']=='TOR':
                self.assertEqual(set(r['filing_scenarios']),{'individual_canada'})
            else:
                self.assertEqual(set(r['filing_scenarios']),{'single','mfj'})
                selected='mfj' if profile['marital_status']=='married' else 'single'
                self.assertEqual(r['filing_scenario']['status'],selected)
                self.assertEqual(r['estimated_net_usd'],r['filing_scenarios'][selected]['estimated_net_usd'])
            for scenario in r['filing_scenarios'].values():
                self.assertAlmostEqual(r['gross_usd']-scenario['estimated_tax_usd'],scenario['estimated_net_usd'],places=2)

    def test_joint_tax_tables_reach_all_away_states_and_locals(self):
        r=self.result('库里',{'filing_status':'mfj'})
        for y in r['years']:
            self.assertEqual(y['resident_state_detail']['filing_status'],'mfj')
            self.assertEqual(y['resident_state_detail']['standard_deduction'],11800)
            self.assertEqual(y['national_detail']['deduction'],32200)
            for away in y['away_states']:
                self.assertEqual(away['detail']['filing_status'],'mfj')
        single=west.calculate_portland(1_000_000,filing_status='single',metro_resident=True,multnomah_resident=True)
        joint=west.calculate_portland(1_000_000,filing_status='mfj',metro_resident=True,multnomah_resident=True)
        self.assertLess(joint['tax'],single['tax'])

    def test_spouse_wages_stay_home_and_payroll_is_individual(self):
        a=self.result('库里',{'filing_status':'mfj'})
        b=self.result('库里',{'filing_status':'mfj','spouse_wages_2026':200000,'spouse_wages_2027':200000})
        for x,y in zip(a['years'],b['years']):
            self.assertAlmostEqual(y['household_gross']-y['annualized_gross'],200000)
            self.assertEqual(y['components']['national_employee_payroll'],y['national_detail']['payroll_by_person']['primary']['payroll'])
            self.assertAlmostEqual(x['components']['extra_employee_payroll'],y['components']['extra_employee_payroll'],places=4)
            for u,v in zip(x['away_states'],y['away_states']):
                self.assertAlmostEqual(u['source_income'],v['source_income'],places=4)
            self.assertLess(abs(sum(y['components'].values())-y['total_tax']),.00001)

    def test_unsupported_filing_identity_never_silently_falls_back(self):
        for scenario in [{'filing_status':'mfs'},{'filing_status':'single','spouse_wages_2026':1000}]:
            with self.assertRaises(ValueError):self.result('库里',scenario)
        tor=next(p for p in self.s['players'] if p['teams_in_active_roster_sections']==['TOR'])
        with self.assertRaises(ValueError):estimate_player(tor,self.s,self.p,self.g,{'filing_status':'mfj'})

    def test_nonresident_surtax_and_exemptions(self):
        r=east.source_tax('MA',50_000_000,.01,2026,resident_state='TX')
        self.assertAlmostEqual(r['tax'],24897.8,places=2)
        r=west.calculate_nonresident('CA',50_000_000,.01)
        self.assertEqual(r['surtax'],0)
        self.assertEqual(east.source_tax('DC',50_000_000,.1)['tax'],0)
        self.assertEqual(east.source_tax('MI',50_000_000,.1,resident_state='IL')['tax'],0)
        self.assertEqual(east.calculate_local('NYC',50_000_000,ratio=.1)['tax'],0)
        self.assertEqual(east.local_credit_limit('DET',100_000),1200)

    def test_full_cache_accounting(self):
        c=self.cache
        self.assertEqual(c['model_fingerprint'],model_fingerprint())
        self.assertEqual(c['count'],520)
        self.assertEqual(len({r['player_id'] for r in c['estimates']}),520)
        self.assertEqual(sum(r['active_roster'] for r in c['estimates']),504)
        for r in c['estimates']:
            self.assertTrue(math.isfinite(r['estimated_net_usd']))
            self.assertGreaterEqual(r['estimated_net_usd'],0)
            self.assertLessEqual(r['estimated_net_usd'],r['gross_usd'])
            self.assertAlmostEqual(r['gross_usd']-r['estimated_tax_usd'],r['estimated_net_usd'],places=2)
            self.assertLess(abs(sum(r['components_usd'].values())-r['estimated_tax_usd']),.08)
            self.assertLessEqual(sum(x['income_share'] for x in r['source_distribution']),1.000000001)

    def test_game_coverage_and_no_duplicate_duty_date(self):
        teams={r['team'] for r in self.cache['estimates']}
        self.assertEqual(len(teams),30)
        self.assertEqual(len(self.g['games']),1200)
        for team in teams:
            self.assertEqual(sum(team in (g['home'],g['away']) for g in self.g['games']),80)
            ledger=make_ledger(team,self.g['games'])
            self.assertEqual(len(ledger),len({r['date'] for r in ledger}))
            self.assertEqual(sum(r['activity']=='scheduled_game' for r in ledger),80)

    def test_injury_assignment_changes_sourcing_not_salary(self):
        baseline=self.result('杨瀚森')
        scenario={'duty_day_overrides':[{'start':'2026-11-01','end':'2026-11-10','country':'US','state':'CA','city':'Stockton','activity':'g_league_game'}]}
        changed=self.result('杨瀚森',scenario)
        self.assertEqual(baseline['gross_usd'],changed['gross_usd'])
        self.assertNotEqual(baseline['estimated_net_usd'],changed['estimated_net_usd'])
        self.assertEqual(changed['duty_summary']['calendar_days'],baseline['duty_summary']['calendar_days'])

    def test_escrow_is_separate_from_final_tax(self):
        base=self.result('库里');changed=self.result('库里',{'escrow_rate':.1,'agent_fee_rate':.04})
        self.assertEqual(base['estimated_net_usd'],changed['estimated_net_usd'])
        cash=changed['cashflow_scenario']
        self.assertAlmostEqual(cash['temporary_escrow_usd'],base['spotrac_salary_usd']*.1,places=2)

    def test_ambiguous_names_and_full_names(self):
        self.assertTrue(requires_clarification(self.s['players'],'鲍尔的薪水',resolve(self.s['players'],'鲍尔的薪水')))
        self.assertGreater(len(resolve(self.s['players'],'布里奇斯的薪水')),1)
        self.assertEqual(self.player('库里')['player'],'Stephen Curry')
        self.assertEqual(self.player('布朗尼詹姆斯')['player'],'Bronny James')
        self.assertEqual(self.player('哈里森巴恩斯')['player'],'Harrison Barnes')

    def test_overseas_bonus_and_dates(self):
        p=next(p for p in self.s['players'] if p['teams_in_active_roster_sections']==['SAS'])
        a=estimate_player(p,self.s,self.p,self.g)
        b=estimate_player(p,self.s,self.p,self.g,{'cup_bonus_usd':500000})
        for y,z in zip(a['years'],b['years']):
            self.assertEqual(y['foreign_ledger'],z['foreign_ledger'])
        gbfr=[(y['year'],r) for y in a['years'] for r in y['foreign_ledger'] if r['country'] in ('GB','FR')]
        self.assertTrue(gbfr)
        self.assertTrue(all(y==2027 for y,r in gbfr))

if __name__=='__main__':unittest.main(verbosity=2)
