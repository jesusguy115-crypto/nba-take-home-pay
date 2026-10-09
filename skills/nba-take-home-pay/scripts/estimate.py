#!/usr/bin/env python3
"""2026–27 NBA wage scenario, with annual tax attribution and auditable credits.

No network, no external dependencies. This models a declared itinerary/residence;
it does not purport to reconstruct an athlete's private payroll or tax returns.
"""
from collections import defaultdict
from pathlib import Path
import hashlib
import json
import math
from functools import lru_cache

from duty_days import TEAMS, home_location, make_ledger, summarize
from data_status import input_file_paths, schedule_uncertainty
import tax_east as east
import tax_west as west
import tax_federal as federal
import escrow

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'assets'
VERSION='2026-27.3.0'
SEASON='2026-27'
CHECKED='2026-10-09'
STATES=set(east.STATES)|set(west.STATES)
CITY_CODES={'New York':'NYC','Brooklyn':'NYC','Philadelphia':'PHI','Cleveland':'CLE',
            'Detroit':'DET','Indianapolis':'MARION'}
WEST_RECIP={'IL':{'IA','KY','MI','WI'},'WI':{'IL','IN','KY','MI'},'MN':{'MI','ND'}}

def load(name):return json.loads((ASSETS/name).read_text())

@lru_cache(maxsize=1)
def player_profiles():
    return load('player-tax-profiles-2026-27.json')['profiles']

def filing_selection(player_id,payer,scenario):
    profile=player_profiles()[str(player_id)]
    requested=scenario.get('filing_status')
    if payer=='TOR':
        if requested not in (None,'individual_canada'):
            raise ValueError('Toronto uses Canadian individual returns; do not apply US single/MFJ return categories')
        return profile,'single','individual_canada','Canadian_individual_return_no_US_joint_return'
    if requested not in (None,'single','mfj'):
        raise ValueError('filing_status supports single/mfj; MFS needs separate community-property and jurisdiction review')
    default='mfj' if profile['marital_status'] in ('married','married_reported') else 'single'
    selected=requested or default
    reason=('user_requested_counterfactual' if requested else
            'reported_married_MFJ_wage_only_assumption' if default=='mfj' else
            'marriage_unverified_single_table_reference_with_MFJ_comparison')
    return profile,selected,selected,reason

def model_fingerprint():
    digest=hashlib.sha256()
    paths=input_file_paths(ROOT)
    for p in paths:
        digest.update(p.name.encode());digest.update(p.read_bytes())
    return digest.hexdigest()

def state_tax(state,gross,year,filing_status='single',spouse_wages=0):
    return (east if state in east.STATES else west).calculate_state(state,gross,year,filing_status=filing_status,spouse_wages=spouse_wages)

def nonresident_tax(state,gross,share,year,residence,filing_status='single',spouse_wages=0):
    if state in east.STATES:return east.source_tax(state,gross,share,year,resident_state=residence,filing_status=filing_status,spouse_wages=spouse_wages)
    result=west.calculate_nonresident(state,gross,share,year,filing_status=filing_status,spouse_wages=spouse_wages)
    if residence in WEST_RECIP.get(state,set()):
        result.update(tax=0.0,ordinary_tax=0.0,surtax=0.0,credit_base=0.0,allocation_status='reciprocal_wage_exemption')
    return result

def local_tax(city,gross,share,year,resident=False,filing_status='single',spouse_wages=0):
    household={'filing_status':filing_status,'spouse_wages':spouse_wages}
    if city in CITY_CODES:
        if city=='Philadelphia' and year==2027:
            early=east.calculate_local('PHI',gross,resident=resident,ratio=share,year=year,pay_date='2027-01-01',**household)
            late=east.calculate_local('PHI',gross,resident=resident,ratio=share,year=year,pay_date='2027-07-01',**household)
            # Of this season's 20 default Jan–Oct payments, 12 precede July.
            return {**early,'tax':early['tax']*.6+late['tax']*.4,
                    'brackets':[], 'payment_periods':[{'weight':.6,'detail':early},{'weight':.4,'detail':late}],
                    'status':'2027_enacted_July_change;season_payment_weight_proxy'}
        return east.calculate_local(CITY_CODES[city],gross,resident=resident,ratio=share,year=year,**household)
    if city=='Portland':
        return west.calculate_portland(gross,year,metro_resident=resident,multnomah_resident=resident,
                                       metro_source_share=share,multnomah_source_share=share,**household)
    return {'tax':0.0,'items':[],'note':'No modeled NBA-venue city income tax'}

def season_foreign_ledgers(salary,active_fraction,ledger):
    """Tax contract wages once per host tax year, then attribute by US service year.

    UK uses April 6–April 5; other supported countries use calendar years.
    A Cup bonus needs its own source allocation and is not part of this pool.
    """
    groups={}
    for row in ledger:
        country='GB' if row['country']=='UK' else row['country']
        if country=='US' or row['weight']<=0:continue
        service_year=int(row['date'][:4])
        if service_year not in (2026,2027):
            raise ValueError('Foreign service outside 2026/2027 requires a separately modeled tax year')
        host_start=service_year-int(country=='GB' and row['date'][5:]<'04-06')
        if host_start not in (2026,2027):
            raise ValueError('UK service before 2026-04-06 requires verified 2025–26 tax parameters')
        groups.setdefault((country,host_start),defaultdict(float))[service_year]+=row['weight']
    by_year={2026:[],2027:[]}
    for (country,host_start),days_by_year in sorted(groups.items()):
        total_days=sum(days_by_year.values())
        total_income=salary*active_fraction*total_days/len(ledger)
        if total_income<=0:continue
        detail=federal.calculate_overseas(country,total_income,host_start)
        host_label=f'{host_start}-{str(host_start+1)[2:]}' if country=='GB' else str(host_start)
        for year,days in sorted(days_by_year.items()):
            fraction=days/total_days
            by_year[year].append({
                'country':country,'weighted_days':days,'source_income':total_income*fraction,
                'tax':detail['tax']*fraction,'foreign_income_tax':detail['tax']*fraction,
                'host_tax_year':host_label,'host_year_source_income':total_income,
                'host_year_tax':detail['tax'],'host_year_allocation_fraction':fraction,
                'host_tax_detail':detail,
                'method':'one_host_tax_calculation;US_service_year_proportional_attribution',
                'sources':detail.get('sources',[]),
            })
    return by_year

def annual(gross,year,residence,base_state,distribution,ledger,*,toronto_mode=False,filing_status='single',spouse_wages=0):
    """Annualized income used to obtain rates. Geography is a SEASON proxy in both years."""
    player_gross=gross
    if toronto_mode and (filing_status!='single' or spouse_wages):
        raise ValueError('Canada uses individual returns; US MFJ/spouse-wage scenarios cannot be applied to Toronto')
    gross=player_gross+spouse_wages
    player_share=player_gross/gross if gross else 1.0
    household={'filing_status':filing_status,'spouse_wages':spouse_wages}
    shares=defaultdict(float);cities=defaultdict(float);countries=defaultdict(float)
    for loc in distribution:
        # Spouse wages are assumed earned entirely at the shared residence,
        # never automatically sent on the player's road itinerary.
        share=loc['income_share']*player_share
        if loc['country']=='US':shares[loc['state']]+=share;cities[(loc['state'],loc['city'])]+=share
        else:countries[loc['country']]+=share
    unknown=set(shares)-STATES
    if unknown:raise ValueError('State not yet covered by tax model: '+','.join(sorted(unknown)))
    rs,rc=residence['state'],residence['city']
    nat=federal.calculate_canada(gross,year) if toronto_mode else federal.calculate_us(gross,year,**household)
    home_state={'tax':nat['provincial'],'credit_base':nat['provincial']} if toronto_mode else state_tax(rs,gross,year,**household)
    home_local={'tax':0.0} if toronto_mode else local_tax(rc,gross,1.0,year,True,**household)
    away=[];away_locals=[]
    for state,share in sorted(shares.items()):
        if state==rs:continue
        detail=nonresident_tax(state,gross,min(1.0,share),year,rs,**household)
        away.append({'state':state,'income_share':share,'source_income':gross*share,
                     'tax_before_credit':detail['tax'],'work_state_credit':0.0,
                     'residence_state_credit':0.0,'detail':detail})
    for (state,city),share in sorted(cities.items()):
        if city==rc or (city in ('Brooklyn','New York') and rc in ('Brooklyn','New York')):continue
        detail=local_tax(city,gross,min(1.0,share),year,**household)
        if detail['tax']:
            away_locals.append({'state':state,'city':city,'income_share':share,'source_income':gross*share,
                                'tax':detail['tax'],'detail':detail})
    resident_credit=work_credit=local_credit=0.0
    credit_rows=[]
    home_credit_base=home_state.get('credit_base',home_state['tax'])
    for row in away:
        state,share=row['state'],row['income_share']
        visitor=row['tax_before_credit']
        # Reverse credit is claimed on the work-state nonresident return.
        reverse=rs in west.DATA['reverse_credit_nonresident_allowed_residents'].get(state,[])
        if reverse and not toronto_mode:
            cap=row['detail'].get('credit_base',visitor)
            credit=min(cap,home_credit_base*share)
            row['work_state_credit']=credit;work_credit+=credit
            method='reverse_credit_on_nonresident_work_state_return'
        elif not toronto_mode:
            eligible=visitor
            if rs in {'NY','MI'}:eligible+=sum(x['tax'] for x in away_locals if x['state']==state)
            # WI Pub125 permits local net-income tax paid directly to the state.
            # The modeled Marion County tax is collected by Indiana DOR.
            if rs=='WI' and state=='IN':
                eligible+=sum(x['tax'] for x in away_locals if x['state']=='IN')
            credit=min(eligible,home_credit_base*share)
            row['residence_state_credit']=credit;resident_credit+=credit
            method='residence_credit_capped_to_same_income;NY_MI_include_local;WI_includes_IN_state_collected_county'
        else:credit=0.0;method='Canadian_country_credit_computed_separately'
        credit_rows.append({'work_state':state,'income_share':share,'credit':credit,'method':method})
    if not toronto_mode and rs=='IL':
        # IL Schedule CR uses one aggregate ceiling, not one ceiling per state.
        # Line1 excludes reciprocal-state wages unless taxed by a city/county;
        # non-Illinois wages from zero-tax jurisdictions remain in Column B.
        # Foreign wages may enter the non-Illinois income ratio, but foreign tax
        # never enters the qualifying US state/local tax pool (instructions 51).
        locals_by_state=defaultdict(float);local_shares_by_state=defaultdict(float)
        for local in away_locals:
            locals_by_state[local['state']]+=local['tax']
            local_shares_by_state[local['state']]+=local['income_share']
        non_il_share=sum(countries.values())
        for row in away:
            state=row['state']
            non_il_share+=(min(row['income_share'],local_shares_by_state[state])
                           if state in WEST_RECIP['IL'] else row['income_share'])
        # Schedule CR line43 requires rounding the ratio to three decimals.
        cr_decimal=min(1.0,math.floor(max(0.0,non_il_share)*1000+0.5)/1000)
        qualifying=sum(r['tax_before_credit']-r['work_state_credit'] for r in away)+sum(locals_by_state.values())
        resident_credit=min(qualifying,home_credit_base*cr_decimal)
        credit_rows=[]
        for row in away:
            eligible=row['tax_before_credit']-row['work_state_credit']+locals_by_state[row['state']]
            credit=resident_credit*eligible/qualifying if qualifying else 0.0
            row['residence_state_credit']=credit
            credit_rows.append({'work_state':row['state'],'income_share':row['income_share'],
                                'credit':credit,'eligible_state_and_local_tax':eligible,
                                'method':'IL_Schedule_CR_aggregate_credit_allocated_for_display',
                                'aggregate_credit_limit':home_credit_base*cr_decimal,
                                'non_Illinois_income_share_before_rounding':non_il_share,
                                'Schedule_CR_decimal':cr_decimal,
                                'source_url':'https://tax.illinois.gov/forms/incometax/currentyear/individual/il-1040-schedule-cr-instr.html'})
    if not toronto_mode and rs=='GA':
        # GA Rule560-7-7-.01(1) aggregates all mutually taxed income and tax;
        # IT-511 p34 includes US local net-income taxes in the eligible pool.
        locals_by_state=defaultdict(float);local_shares_by_state=defaultdict(float)
        for local in away_locals:
            locals_by_state[local['state']]+=local['tax']
            local_shares_by_state[local['state']]+=local['income_share']
        mutual_share=0.0;qualifying=0.0
        for row in away:
            paid=row['tax_before_credit']-row['work_state_credit']
            qualifying+=paid+locals_by_state[row['state']]
            mutual_share+=(row['income_share'] if paid>0 else
                           min(row['income_share'],local_shares_by_state[row['state']]))
        credit_limit=home_credit_base*min(1.0,mutual_share)
        resident_credit=min(qualifying,credit_limit)
        credit_rows=[]
        for row in away:
            eligible=row['tax_before_credit']-row['work_state_credit']+locals_by_state[row['state']]
            credit=resident_credit*eligible/qualifying if qualifying else 0.0
            row['residence_state_credit']=credit
            credit_rows.append({'work_state':row['state'],'income_share':row['income_share'],
                                'credit':credit,'eligible_state_and_local_tax':eligible,
                                'method':'GA_combined_credit_allocated_for_display',
                                'aggregate_credit_limit':credit_limit,
                                'mutually_taxed_income_share':mutual_share,
                                'source_url':'https://rules.sos.ga.gov/gac/560-7-7'})
    # Resident municipal credits; NYC deliberately has none. Detroit cap is 1.2%.
    local_credit_rows=[]
    if not toronto_mode and rc in CITY_CODES:
        code=CITY_CODES[rc]
        for row in away_locals:
            if rs=='IN' and row['state']=='IN':continue
            if code in {'CLE','DET'} and row['city'] not in {'New York','Brooklyn','Philadelphia','Cleveland','Detroit'}:
                continue  # Other-city credits do not automatically cover county/Metro taxes.
            cap=east.local_credit_limit(code,row['source_income'])
            if code=='PHI' and gross:cap=home_local['tax']*row['source_income']/gross
            credit=min(row['tax'],cap)
            if credit:
                local_credit+=credit
                local_credit_rows.append({'work_city':row['city'],'credit':credit,'method':'resident_local_credit_on_same_income'})
    if not toronto_mode and rc=='Portland':
        # Portland policy permits each local credit independently of the Oregon credit,
        # but bars it where the work state grants the reverse nonresident credit.
        for row in away:
            if row['residence_state_credit']<=0 or row['work_state_credit']>0:continue
            for local in home_local['items']:
                credit=min(local['tax']*row['income_share'],row['tax_before_credit'],local['tax'])
                local_credit+=credit
                local_credit_rows.append({'work_state':row['state'],'local':local['name'],'credit':credit,
                                         'method':'Portland_policy_local_net_tax_times_mutually_taxed_AGI_share'})
    local_credit=min(local_credit,home_local['tax']*player_share)
    extra_payroll=west.calculate_payroll(base_state,player_gross,year,residence_state=rs,oregon_source_share=shares.get('OR',0)/player_share if player_share else 0)
    payroll_rows=extra_payroll['items']
    if base_state in east.STATES:payroll_rows+=east.employee_payroll(base_state,player_gross,year)
    # Denver OPT is a wage charge, not creditable local income tax.
    denver_months=defaultdict(float)
    for row in ledger:
        if row['country']=='US' and row['city']=='Denver':
            denver_months[row['date'][:7]]+=player_gross*row['weight']/max(1,len(ledger))
    if denver_months:
        opt=west.calculate_denver_opt(denver_months)
        payroll_rows.append({'name':'DENVER_OPT_SCENARIO','tax':opt['tax'],
                             'note':'Season-month proxy reused in each annualized model','detail':opt})
    foreign=[];ftc_details=[];foreign_credit=0.0
    if toronto_mode:
        # Provincial/federal final income tax can credit eligible US state/local tax
        # even when the US federal wage is treaty-exempt. No duplicate US FICA.
        foreign_tax=sum(r['tax_before_credit']-r['work_state_credit'] for r in away)+sum(r['tax'] for r in away_locals)
        taxed_states={r['state'] for r in away if r['tax_before_credit']>0}
        us_income_share=sum(shares[s] for s in taxed_states)
        for loc in away_locals:
            if loc['state'] not in taxed_states:us_income_share+=loc['income_share']
        ftc=federal.canada_foreign_tax_credit(nat,foreign_tax,gross*min(1,us_income_share))
        foreign_credit=ftc['credit'];ftc_details.append({'country':'US',**ftc})
        # Current Toronto schedule has no third-country games; fail explicitly if overridden.
        if any(c not in ('CA',) and v>0 for c,v in countries.items()):
            raise ValueError('Toronto third-country scenario needs a separately verified Canadian treaty model')
    # US-team overseas final taxes are calculated once per actual service year in
    # estimate_player; annualizing a single foreign trip would distort its brackets.
    components={
        'federal_income_tax':nat['federal']*player_share,
        'national_employee_payroll':nat['payroll'] if toronto_mode else nat['payroll_by_person']['primary']['payroll'],
        'resident_state_province_tax':home_state['tax']*player_share,
        'away_state_tax':sum(r['tax_before_credit'] for r in away),
        'residence_state_credit':-resident_credit,
        'work_state_credit':-work_credit,
        'resident_local_tax':home_local['tax']*player_share,
        'away_local_tax':sum(r['tax'] for r in away_locals),
        'resident_local_credit':-local_credit,
        'extra_employee_payroll':sum(r['tax'] for r in payroll_rows),
        'foreign_income_tax':sum(r['tax'] for r in foreign),
        'foreign_tax_credit':-foreign_credit,
    }
    total=sum(components.values())
    return {'year':year,'annualized_gross':player_gross,'household_gross':gross,'spouse_wages':spouse_wages,
            'player_share_of_household_wages':player_share,'filing_status':filing_status,
            'household_allocation_method':'income_tax_proportional_to_wages;individual_payroll;player_road_taxes_and_credits_attributed_to_player',
            'components':components,'total_tax':total,'net':player_gross-total,
            'national_detail':nat,'resident_state_detail':home_state,'resident_local_detail':home_local,
            'away_states':away,'away_locals':away_locals,'state_credit_ledger':credit_rows,
            'local_credit_ledger':local_credit_rows,'extra_payroll_ledger':payroll_rows,
            'foreign_ledger':foreign,'foreign_credit_ledger':ftc_details}

def _estimate_player_core(player,salaries,previous,schedule,scenario=None,full=True):
    scenario=scenario or {}
    allowed={'residence_state','residence_city','duty_day_overrides','cup_bonus_usd','agent_fee_rate','escrow_rate','annual_income_2026','annual_income_2027','filing_status','spouse_wages_2026','spouse_wages_2027'} | escrow.SCENARIO_KEYS
    unsupported=set(scenario)-allowed
    if unsupported:raise ValueError('Unknown scenario keys: '+','.join(sorted(unsupported)))
    if any(not math.isfinite(float(scenario[k])) or float(scenario[k])<0 for k in ('cup_bonus_usd','agent_fee_rate','escrow_rate','annual_income_2026','annual_income_2027','spouse_wages_2026','spouse_wages_2027') if k in scenario):
        raise ValueError('Scenario amounts must be finite and nonnegative')
    if float(scenario.get('agent_fee_rate',0))>1:raise ValueError('Agent fee rate must be 0..1')
    settlement=escrow.selection(scenario)
    records_by_id={r['record_id']:r for r in salaries['payment_records']}
    records=[records_by_id[i] for i in player['payment_record_ids']]
    active=[r for r in records if r['source_section']=='Active Roster']
    payer=max(active or records,key=lambda r:r['cash_total_usd'])['team']
    profile,filing_status,public_filing_status,selection_reason=filing_selection(player['player_id'],payer,scenario)
    spouse_by_year={year:float(scenario.get(f'spouse_wages_{year}',0)) for year in (2026,2027)}
    if any(spouse_by_year.values()) and (filing_status!='mfj' or payer=='TOR'):
        raise ValueError('Spouse wages require a US MFJ scenario; Canadian family credits need individualized analysis')
    home=home_location(payer)
    rs=scenario.get('residence_state',home['state']).upper()
    if rs not in STATES|{'ON'}:raise ValueError('Unsupported resident jurisdiction: '+rs)
    if (rs=='ON')!=(payer=='TOR'):raise ValueError('Cross-border residence change requires individualized treaty/coverage analysis')
    rc=scenario.get('residence_city',home['city'] if rs==home['state'] else '')
    city_state={v[2]:v[1] for v in TEAMS.values()}
    if rc and (rc not in city_state or city_state[rc]!=rs):raise ValueError('Residence city must be a supported NBA city in the selected state; omit for no city-tax assumption')
    residence={'country':'CA' if rs=='ON' else 'US','state':rs,'city':rc}
    contract_salary=float(player['cash_total_usd']);bonus=float(scenario.get('cup_bonus_usd',0))
    salary=contract_salary*(1-settlement['final_reduction_rate'])+settlement['settlement_bonus_usd']
    gross=salary+bonus
    ledger=make_ledger(payer,schedule['games'],scenario.get('duty_day_overrides'))
    duty=summarize(ledger)
    active_salary=sum(r['cash_total_usd'] for r in active)
    active_fraction=active_salary/contract_salary if contract_salary else 0
    # Non-service retained/buyout payments have no evidenced current duty dates.
    # Tax them in the assumed residence; do not invent road service for those dollars.
    locations=[{**x,'income_share':x['income_share']*active_fraction} for x in duty['locations']]
    prior=next((x for x in previous['players'] if x['player_id']==player['player_id']),None)
    prior_gross=float(prior['cash_total_usd']) if prior else contract_salary
    adjusted_prior_gross=prior_gross*(1-settlement['prior_season_final_reduction_rate'])
    annual_gross={2026:float(scenario.get('annual_income_2026',adjusted_prior_gross*5/6+salary/6+bonus)),
                  2027:float(scenario.get('annual_income_2027',salary))}
    parts={2026:salary/6+bonus,2027:salary*5/6}
    foreign_by_year=season_foreign_ledgers(salary,active_fraction,ledger) if payer!='TOR' else {}
    years=[];components=defaultdict(float)
    for year in (2026,2027):
        if annual_gross[year]+1e-8<parts[year]:raise ValueError('Annual income cannot be below season payments allocated to that year')
        a=annual(annual_gross[year],year,residence,home['state'],locations,ledger,toronto_mode=payer=='TOR',filing_status=filing_status,spouse_wages=spouse_by_year[year])
        fraction=parts[year]/annual_gross[year] if annual_gross[year] else 0
        attributed={k:v*fraction for k,v in a['components'].items()}
        if payer!='TOR':
            foreign=foreign_by_year[year]
            foreign_paid=sum(x['tax'] for x in foreign)
            foreign_income=sum(x['source_income'] for x in foreign)
            ftc=federal.us_foreign_tax_credit(a['national_detail']['federal'],foreign_paid,foreign_income,a['household_gross'])
            credit=min(ftc['credit'],attributed['federal_income_tax'])
            attributed['foreign_income_tax']=foreign_paid
            attributed['foreign_tax_credit']=-credit
            a['foreign_ledger']=foreign
            a['foreign_credit_ledger']=[{**ftc,'season_credit_applied':credit,'basis':'modeled_service_year_contract_salary;one_host_tax_year_calculation;annual_US_limitation;CA_income_included;Cup_bonus_source_not_inferred'}]
        for k,v in attributed.items():components[k]+=v
        a.update(season_payment=parts[year],season_attribution_fraction=fraction,
                 season_attributed_components=attributed,season_attributed_tax=sum(attributed.values()))
        years.append(a)
    tax=sum(components.values());net=gross-tax
    assumptions=[
        f'本次计算身份为{public_filing_status}情景，真实税务申报身份未知；婚姻事实、申报方式及配偶收入分别记录。',
        f'居民地是假设的 {rs} {rc or "不计居民城市税"}；不代表查明了球员真实住所或申报身份。',
        '按已公布赛程假设全程随队；非比赛日位置和0.5天旅行/训练权重属于模型，不是实际行程或各州法定工作日认证。',
        '训练营/季前赛期间默认在球队城市；未覆盖实际异地训练营、季前赛、全明星和季后赛行程。',
        schedule_uncertainty(schedule,payer),
        '2026–27赛季按24期默认工资表分配：2026年1/6、2027年5/6；按年度平均税率归属，不是独立报税表。',
        '2026年度收入参考上赛季现金薪资；2027以本赛季薪资年化，不预测未来合同或交易；两年地理比例统一用本赛季代理行程。',
        '2027尚未核定的税档、扣除和社保上限使用2026代理；已核实的已立法变化单独应用。',
        '工资覆盖地默认球队所在地；部分雇员保险按法定最大雇员份额，球队代付或私人计划会改变扣款。',
        '跨州分摊和抵免按公开规则简化；州级境外抵免、税表个别调整和历史结转未全面模拟。',
        f'本赛季最终工资扣减按{settlement["final_reduction_rate"]:.2%}情景重算所有税项，2026–27实际结算未知；默认5.48%仅参考2025–26报道，非预测。',
        f'上赛季工资按{settlement["prior_season_final_reduction_rate"]:.2%}最终扣减代理2026年度收入；未核实个人上季结算或付款税年。',
        '暂扣与最终扣减分别记录，不重复扣钱；本赛季结算后工资按24期比例归属税年，不认定返还时才计税或具体到账日期。',
        '税后估值不扣未知经纪费和个人自愿扣款；暂扣明细仅报告税前现金流，不等于银行到账。',
    ]
    flags=[f'联盟结算：2026–27实际扣减率未知，本次用{settlement["final_reduction_rate"]:.2%}假设；默认5.48%来自上季汇总报道，不能视为本季或个人已定结果。',
           f'跨年托管税务：暂按调整后的工资比例归属2026/2027税年，上季扣减假设{settlement["prior_season_final_reduction_rate"]:.2%}；实际付款、退款与税表处理可能不同。']
    if settlement['settlement_bonus_usd']:
        flags.append('联盟补发采用用户指定金额，并按合同服务地比例及24期税年归属代理征税；这不是已确认的补发或发薪日期。')
    if 'annual_income_2026' in scenario or 'annual_income_2027' in scenario:
        flags.append('用户年度收入覆盖值视为联盟结算调整后的全年工资；模型不再对覆盖值扣减，基准比较同步撤销本季归属该年的结算调整，保持指定的其他年度收入不变。')
    if payer!='TOR':
        if filing_status=='mfj' and not any(spouse_by_year.values()):
            flags.append('夫妻合报情景只纳入球员工资，配偶收入未纳入模型，不代表配偶实际没有收入；实际申报方式与家庭税负归属仍未知。')
        elif filing_status=='mfj':
            flags.append('使用用户指定配偶工资，假定配偶全在共同居民地履职；共同所得税按两人工资比例分配，球员客场税及其抵免归球员，不等同私人税单分配。')
        if profile['marital_status'] not in ('married','married_reported'):
            flags.append('婚姻资料未核实或不足以确认税年末状态；Single/MFJ均为工资测算情景，不将资料未知认定为单身。')
        elif filing_status=='single':
            flags.append('公开资料记录已婚；本次Single只是用户指定比较情景，不表示该球员依法可按Single申报。')
        else:
            flags.append('公开已婚资料用于选择MFJ估算情景；历史婚姻记录不证明2026/2027年末状态，也不证明其实际联合报税。')
    else:
        flags.append('加拿大按个人申报，不套美国夫妻合报税档；配偶相关低收入抵免及家庭情况未全面模拟。')
    if not prior:flags.append('未找到上赛季Spotrac工资；以本季合同金额及上季扣减假设代理上季工资，初入联盟或跨国转会误差可能更大。')
    if any(y['household_gross']<80000 for y in years):
        flags.append('至少一个年度的家庭工资代理低于8万美元；低收入、子女、年龄、住房等专项或可退税抵免未全面模拟，误差可能更明显。')
    if active_fraction<1:flags.append('包含Dead Money/Retained等非当前服务付款；来源暂按假定居民地，且最终扣减率统一用于Spotrac现金额；实际适用扣减及工资性质需逐笔核定。')
    if player.get('signing_bonus_usd',0):flags.append('Spotrac包含签约金，当前按合同现金收入统一套用结算扣减及来源分配；实际适用基数、归属和发放时间可能不同。')
    if scenario.get('duty_day_overrides'):flags.append('已使用个人日期覆盖；伤病名单、私人康复、G联赛地点及各州分母差异仍需个别核定，不能把此覆盖当成报税结论。')
    if payer=='TOR':flags.append('猛龙明确采用加拿大安省税务居民、非美国公民、符合加美协定且US访客工资满足豁免条件、加拿大CPP/EI覆盖的假设情景；这些不是已核实的球员身份，美国公民等情形须另算。')
    if bonus:flags.append('杯赛奖金单列加入2026年税基，不套合同暂扣或最终扣减率；境外来源暂仅按调整后合同及联盟补发分摊，奖金实际来源及协定待遇需另核。')
    if any(x['country'] not in ('US','CA') and x['income_share']>0 for x in locations):flags.append('含海外比赛：用固定汇率与境外税则代理估算；实际跨国分摊、费用、协定及最终抵免可能不同。')
    if rs in ('NY','OR','PA','OH','MI','IN') and rc:flags.append('假设住在球队所在城市/县；实际住在郊区或另一税区，地方税可明显不同。')
    result={
        'season':SEASON,'model_version':VERSION,'captured_date':salaries['captured_date'],'tax_checked_date':CHECKED,
        'player_id':player['player_id'],'player':player['player'],'team':payer,'team_zh':TEAMS[payer][0],
        'active_roster':bool(active),'paying_teams':player['paying_teams'],'currency':'USD',
        'tax_profile':profile,
        'filing_scenario':{'status':public_filing_status,'selection_reason':selection_reason,
            'actual_filing_status':profile['actual_filing_status'],
            'spouse_wages_by_year':spouse_by_year,
            'spouse_income_status':'user_supplied_wages' if any(spouse_by_year.values()) else 'not_included_in_wage_only_scenario_not_verified_zero',
            'family_tax_allocation':'proportional_income_tax;individual_payroll;player_road_taxes_and_credits_to_player'},
        'spotrac_salary_usd':contract_salary,'extra_cup_bonus_usd':bonus,'gross_usd':gross,
        'contract_gross_usd':contract_salary+bonus,'extra_settlement_bonus_usd':settlement['settlement_bonus_usd'],
        'escrow_scenario':settlement,'cashflow_scenario':escrow.cashflow(contract_salary,bonus,settlement),
        'estimated_net_usd':round(gross-round(tax,2),2),'rounded_net_usd':int(round(net/10000))*10000,
        'estimated_tax_usd':round(tax,2),'effective_tax_rate':tax/gross if gross else 0,
        'components_usd':{k:round(v,2) for k,v in components.items()},
        'residence_scenario':residence,'previous_season_gross_usd':prior_gross,
        'previous_season_adjusted_gross_usd':adjusted_prior_gross,
        'crossborder_scenario':({'tax_residence':'Canada_Ontario','us_citizen':False,
            'treaty_eligible':True,'US_visitor_wage_exemption_conditions_satisfied':True,
            'social_security_coverage':'Canada_CPP_EI',
            'status':'explicit_model_assumptions_not_verified_player_facts'} if payer=='TOR' else
            {'tax_residence':'US','treaty_eligible':True,
             'status':'explicit_model_assumptions_not_verified_player_facts'}),
        'previous_season_salary_found':prior is not None,
        'duty_summary':duty,'source_distribution':locations,
        'assumptions':assumptions,'specific_uncertainties':flags,
        'sources':{'salary':player['player_url'],'salary_team_tables':sorted({r['source_url'] for r in records}),
                   'schedule':schedule['source_url'],'rules':'references/tax-sources.md'},
        'calculation_type':'modeled_settlement_adjusted_after_tax_income_not_bank_deposit',
        'years':years if full else [{k:y[k] for k in ('year','annualized_gross','household_gross','spouse_wages','player_share_of_household_wages','season_payment','season_attribution_fraction','season_attributed_components','season_attributed_tax')} for y in years],
    }
    if scenario.get('agent_fee_rate'):
        fees=(contract_salary+bonus)*float(scenario['agent_fee_rate'])
        result['cashflow_scenario'].update(agent_fee_usd=round(fees,2),
            agent_fee_base='original_contract_cash_plus_Cup_bonus;user_supplied_rate',
            net_after_assumed_agent_fee_usd=round(net-fees,2))
    return result


def estimate_player(player,salaries,previous,schedule,scenario=None,full=True):
    """Selected settlement and tax scenario plus its comparable contract baseline.

    Baseline holds prior-season adjustments, residence, filing and itinerary fixed,
    and removes only this season's final reduction and supplemental reconciliation.
    Neither estimate is an assertion of actual W-2 timing or bank deposits.
    """
    scenario=dict(scenario or {})
    result=_estimate_player_core(player,salaries,previous,schedule,scenario,full)
    selected=result['escrow_scenario']
    if selected['final_reduction_rate'] or selected['settlement_bonus_usd']:
        baseline_scenario={**scenario,'final_reduction_rate':0,'settlement_bonus_usd':0}
        undo_adjustment=result['spotrac_salary_usd']*selected['final_reduction_rate']-selected['settlement_bonus_usd']
        for year, fraction in ((2026,1/6),(2027,5/6)):
            key=f'annual_income_{year}'
            if key in scenario:
                baseline_scenario[key]=float(scenario[key])+undo_adjustment*fraction
        baseline=_estimate_player_core(player,salaries,previous,schedule,baseline_scenario,False)
    else:
        baseline=result
    baseline_impact={'gross_reduction_usd':0.0,'supplemental_payment_usd':0.0,
                     'net_gross_adjustment_usd':0.0,'tax_reduction_usd':0.0,'net_reduction_usd':0.0}
    baseline['settlement_impact']=baseline_impact
    baseline_snapshot={key:baseline[key] for key in escrow.SNAPSHOT_FIELDS}
    baseline_snapshot['comparison_basis']='same_prior_season_adjustment;current_final_reduction_and_supplemental_payment_zero'
    result['contract_baseline']=baseline_snapshot
    result['settlement_impact']={
        'gross_reduction_usd':round(result['spotrac_salary_usd']*selected['final_reduction_rate'],2),
        'supplemental_payment_usd':selected['settlement_bonus_usd'],
        'net_gross_adjustment_usd':round(result['gross_usd']-baseline['gross_usd'],2),
        'tax_reduction_usd':round(baseline['estimated_tax_usd']-result['estimated_tax_usd'],2),
        'net_reduction_usd':round(baseline['estimated_net_usd']-result['estimated_net_usd'],2),
    }
    return result
