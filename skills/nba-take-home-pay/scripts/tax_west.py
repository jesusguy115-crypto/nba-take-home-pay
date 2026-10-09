"""Auditable Single/MFJ wages-only state estimates; checked 2026-10-09.

These are scenario liabilities, not completed resident/nonresident tax returns.
The caller supplies actual or modeled source shares and applies cross-state credits.
``gross`` is household wages, including ``spouse_wages``. Payroll takes one
employee's wages instead. Run this module directly for numeric regression checks.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

DATA = json.loads(Path(__file__).with_name('tax-west.json').read_text())
STATES = DATA['states']


def _valid_amount(value, name='gross'):
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f'{name} must be finite and nonnegative')
    return value


def _progressive(income, schedule):
    details = []
    for index, bracket in enumerate(schedule):
        lower = bracket['threshold']
        upper = schedule[index + 1]['threshold'] if index + 1 < len(schedule) else None
        base = max(0., min(income, upper if upper is not None else income) - lower)
        details.append({'lower': lower, 'upper': upper, 'rate': bracket['rate'],
                        'taxable_slice': round(base, 6), 'tax': round(base * bracket['rate'], 6)})
    return sum(row['tax'] for row in details), details


def _filing_inputs(gross, filing_status, spouse_wages):
    if filing_status not in ('single', 'mfj'):
        raise ValueError('filing_status must be single or mfj; MFS is not Single')
    gross = _valid_amount(gross)
    spouse_wages = _valid_amount(spouse_wages, 'spouse_wages')
    if spouse_wages > gross:
        raise ValueError('spouse_wages is included in gross and cannot exceed it')
    if filing_status == 'single' and spouse_wages:
        raise ValueError('single does not accept spouse_wages')
    return gross, spouse_wages


def _rules(code, filing_status):
    rules = STATES[code]
    return {**rules, **rules.get('mfj', {})} if filing_status == 'mfj' else rules


def _federal_2026(gross, filing_status):
    # Oregon subtracts federal income tax, excluding payroll taxes and EITC.
    thresholds = ([0, 24800, 100800, 211400, 403550, 512450, 768700]
                  if filing_status == 'mfj' else
                  [0, 12400, 50400, 105700, 201775, 256225, 640600])
    schedule = [{'threshold': t, 'rate': r} for t, r in
                zip(thresholds, [.10, .12, .22, .24, .32, .35, .37])]
    return _progressive(max(0, gross - (32200 if filing_status == 'mfj' else 16100)), schedule)[0]


def _federal_2026_single(gross):
    """Backward compatible internal helper."""
    return _federal_2026(gross, 'single')


def calculate_state(code, gross, year=2026, filing_status='single', spouse_wages=0):
    """Resident annual liability before other-state credits, locals and payroll.

    gross includes spouse_wages; both spouses are under 65 with no dependents.
    year=2027 carries 2026 parameters explicitly as a proxy. Credits requiring
    facts not accepted here are disclosed, especially for low-income scenarios.
    """
    if year not in (2026, 2027):
        raise ValueError('Only 2026 and explicit 2027 proxy scenarios supported')
    code = code.upper()
    gross, spouse_wages = _filing_inputs(gross, filing_status, spouse_wages)
    rules = _rules(code, filing_status)
    deduction = float(rules['deduction'])
    adjustments = []
    exemption = 0.
    credit = 0.
    if code == 'CO' and gross > rules['deduction_cap']['agi_above']:
        cap = rules['deduction_cap']['cap']
        adjustments.append({'name': 'High-income federal deduction addback',
                            'amount': deduction - cap, 'direction': 'increase_taxable_income'})
        deduction = float(cap)
    elif code == 'MN':
        phaseout = rules['deduction_phaseout']
        reduction = min(deduction * phaseout['max_reduction_fraction'],
                        phaseout['rate1'] * max(0, min(gross, phaseout['threshold2']) - phaseout['threshold1'])
                        + phaseout['rate2'] * max(0, gross - phaseout['threshold2']))
        deduction -= reduction
        adjustments.append({'name': 'MN standard deduction phaseout', 'amount': reduction,
                            'direction': 'reduce_deduction'})
    elif code == 'WI':
        phaseout = rules['deduction_phaseout']
        deduction = (0. if gross >= phaseout['zero_at'] else
                     max(0., deduction - phaseout['rate'] * max(0., gross - phaseout['threshold'])))
        exemption = float(rules['exemption']['amount'])
        if filing_status == 'mfj':
            credit = .03 * min(16000., spouse_wages, gross - spouse_wages)
    elif code == 'OK':
        exemption = float(rules['exemption']['amount'])
    elif code == 'IL':
        exemption = float(rules['exemption']['amount']) if gross <= rules['exemption']['agi_limit'] else 0.
    elif code == 'OR':
        sub = rules['federal_tax_subtraction']
        fed_cap = (sub['max'] if gross < sub['phaseout_start'] else
                   max(0., sub['max'] - sub['reduction_per_step'] *
                       (1 + math.floor((gross - sub['phaseout_start']) / sub['phaseout_step']))))
        fed_subtraction = min(_federal_2026(gross, filing_status), fed_cap)
        deduction += fed_subtraction
        adjustments.append({'name': 'Oregon federal income tax subtraction',
                            'amount': fed_subtraction, 'direction': 'reduce_taxable_income',
                            'note': 'Wages-only federal liability proxy; zero at ordinary NBA salaries'})
        credit = float(rules['exemption']['amount']) if gross <= rules['exemption']['agi_limit'] else 0.
    elif code == 'CA':
        ex = rules['exemption']
        credit = max(0., ex['amount'] - ex['reduction_per_step'] *
                     math.ceil(max(0., gross - ex['phaseout_start']) / ex['phaseout_step']))
        if gross > ex['phaseout_start'] and credit:
            adjustments.append({'name': 'Personal exemption phaseout',
                                'note': '2025 AGI start used as explicit proxy; 2026 credit amount is enacted'})
    elif code == 'UT':
        ex = rules['exemption']
        credit = max(0., ex['base_deduction'] * ex['credit_rate'] -
                     ex['phaseout_rate'] * max(0., gross - ex['phaseout_start']))
        if credit:
            adjustments.append({'name': 'Taxpayer tax credit',
                                'note': '2025 phaseout start proxy; fully phased out for normal NBA wages'})
    taxable = max(0., gross - deduction - exemption)
    before_credit, brackets = _progressive(taxable, rules['brackets'])
    marriage_credit = 0.
    if code == 'MN' and filing_status == 'mfj':
        # Statute 290.0675 uses HALF THE UNPHASED joint standard deduction.
        lesser = min(taxable, max(0., min(spouse_wages, gross - spouse_wages) -
                                 rules['marriage_credit']['lower_earner_deduction']))
        single_tax = (_progressive(lesser, STATES['MN']['brackets'])[0] +
                      _progressive(taxable - lesser, STATES['MN']['brackets'])[0])
        marriage_credit = max(0., before_credit - single_tax)
        credit += marriage_credit
        adjustments.append({'name': 'Minnesota marriage penalty credit',
                            'lesser_earner_after_half_standard_deduction': lesser,
                            'two_single_schedule_tax': round(single_tax, 6),
                            'amount': round(marriage_credit, 6), 'direction': 'reduce_tax',
                            'status': 'statutory_continuous_formula_not_rounded_M1MA_table'})
    elif code == 'WI' and filing_status == 'mfj':
        marriage_credit = credit
    credit = min(credit, before_credit)
    marriage_credit = min(marriage_credit, credit)
    ordinary = max(0., before_credit - credit)
    if exemption:
        adjustments.append({'name': 'Personal exemption deduction', 'amount': exemption,
                            'direction': 'reduce_taxable_income'})
    if credit and not (code == 'MN' and filing_status == 'mfj'):
        adjustments.append({'name': 'Wisconsin married couple credit' if code == 'WI' and filing_status == 'mfj'
                            else 'Nonrefundable personal/taxpayer credit', 'amount': credit,
                            'direction': 'reduce_tax'})
    surtax = .01 * max(0., taxable - 1000000.) if code == 'CA' else 0.
    if surtax:
        adjustments.append({'name': 'Behavioral Health Services Tax', 'amount': surtax,
                            'rate': .01, 'threshold': 1000000, 'direction': 'increase_tax'})
    low_income = 0 < gross < DATA['low_income_scope']['screening_gross'] and code != 'TX'
    return {'code': code, 'year': year, 'parameter_year': 2026, 'gross': gross,
            'filing_status': filing_status, 'spouse_wages': spouse_wages,
            'player_wages': gross - spouse_wages, 'income_scope': 'household' if filing_status == 'mfj' else 'individual',
            'tax': round(ordinary + surtax, 6), 'ordinary_tax': round(ordinary, 6),
            'surtax': round(surtax, 6), 'credit_base': round(ordinary, 6),
            'taxable_income': round(taxable, 6), 'deduction': round(deduction, 6),
            'standard_deduction': rules['deduction'], 'personal_exemption': exemption,
            'personal_credit': round(credit, 6), 'marriage_credit': round(marriage_credit, 6),
            'tax_before_credits': round(before_credit, 6), 'brackets': brackets, 'adjustments': adjustments,
            'credit_scope': 'Modeled personal/taxpayer and marriage credits only; no dependents, age, rent or refundable credits',
            'scope_status': DATA['low_income_scope']['status'] if low_income else 'wages_only_standard_deduction_scenario',
            'scope_notes': [DATA['low_income_scope']['note']] if low_income else [],
            'source_ids': rules['source_ids'],
            'status': rules['status'] if year == 2026 else '2026_parameters_proxy_for_2027',
            'parameter_status': rules['status']}


def calculate_nonresident(code, gross, share, year=2026, filing_status='single', spouse_wages=0):
    """Modeled household share; OR source brackets and CA source surtax differ.

    Caller must first decide reciprocity/exemption eligibility. This simplified
    allocation is not a statutory claim that every state uses identical denominators.
    For MFJ, share is player source wages / household wages; the spouse earns
    wages only in the shared resident state and has zero wages in this work state.
    """
    share = _valid_amount(share, 'share')
    if share > 1:
        raise ValueError('share must be in [0,1]')
    code = code.upper()
    resident = calculate_state(code, gross, year, filing_status, spouse_wages)
    ordinary = resident['ordinary_tax'] * share
    sourced_taxable = resident['taxable_income'] * share
    surtax = .01 * max(0., sourced_taxable - 1000000) if code == 'CA' else 0.
    credit = resident['personal_credit'] * share
    marriage_credit = resident['marriage_credit'] * share
    allocation_status = 'modeled_source_share_and_proportional_deductions'
    brackets = resident['brackets']
    bracket_scope = 'full_household_before_source_allocation'
    tax_before_credits = resident['tax_before_credits'] * share
    if code == 'OR':
        tax_before_credits, brackets = _progressive(sourced_taxable, _rules(code, filing_status)['brackets'])
        credit = min(credit, tax_before_credits)
        ordinary = max(0., tax_before_credits - credit)
        bracket_scope = 'oregon_source_taxable_income'
        allocation_status = 'OR_40_N_source_income_brackets_with_proportional_deductions_and_exemption_credit'
    elif code == 'WI' and filing_status == 'mfj':
        # 1NPR Schedule 2 requires BOTH spouses to have Wisconsin wages. The
        # caller's road-state scenario has zero spouse work-state wages.
        marriage_credit = 0.
        credit = marriage_credit
        ordinary = max(0., tax_before_credits - credit)
    return {**resident, 'resident_full_income_tax': resident['tax'], 'source_share': share,
            'source_taxable_income': round(sourced_taxable, 6),
            'ordinary_tax': round(ordinary, 6), 'surtax': round(surtax, 6),
            'personal_credit': round(credit, 6), 'marriage_credit': round(marriage_credit, 6),
            'tax_before_credits': round(tax_before_credits, 6),
            'brackets': brackets, 'bracket_scope': bracket_scope,
            'resident_full_income_brackets': resident['brackets'],
            'adjustments_scope': 'full_household_resident_calculation_before_source_allocation',
            'credit_base': round(ordinary, 6), 'tax': round(ordinary + surtax, 6),
            'allocation_status': allocation_status,
            'spouse_source_assumption': 'spouse_wages_only_in_shared_resident_state;zero_in_this_nonresident_state' if filing_status == 'mfj' else 'not_applicable',
            'note': 'OR-40-N taxes source taxable income directly; CA surtax uses CA-source taxable income above $1m; interstate credits are separate'}


def calculate_payroll(base_state, gross, year=2026, *, residence_state=None, oregon_source_share=0.):
    """Extra employee payroll charges excluding FICA, under disclosed coverage.

    gross is this employee's own wages, never MFJ combined household wages.
    Employment coverage follows base of operations by assumption; do not impose
    CA SDI or PFML on every visiting athlete. OR transit follows income source.
    No UI/ETT/TriMet employer taxes are deducted from the player.
    """
    if year not in (2026, 2027):
        raise ValueError('Only 2026 and 2027 supported')
    gross = _valid_amount(gross)
    base_state = base_state.upper()
    residence_state = (residence_state or base_state).upper()
    source_share = _valid_amount(oregon_source_share, 'oregon_source_share')
    if source_share > 1:
        raise ValueError('oregon_source_share must be in [0,1]')
    rows = []
    key = {'CA': 'CA_SDI', 'OR': 'OR_PAID_LEAVE', 'CO': 'CO_FAMLI', 'MN': 'MN_PAID_LEAVE'}.get(base_state)
    if key:
        rule = DATA['payroll'][key]
        rate = rule.get('rate_2027', rule['rate']) if year == 2027 else rule['rate']
        base = min(gross, rule['cap']) if rule['cap'] is not None else gross
        rows.append({'name': key, 'rate': rate, 'base': base, 'tax': round(rate * base, 6),
                     'source_ids': rule['source_ids'], 'coverage_assumption': rule['application'],
                     'year_status': '2026_wage_cap_proxy' if year == 2027 and rule['cap'] else 'current_rules'})
    transit_base = gross if residence_state == 'OR' else gross * source_share
    if transit_base > 0:
        rows.append({'name': 'OR_TRANSIT', 'rate': .001, 'base': transit_base,
                     'tax': round(.001 * transit_base, 6), 'source_ids': ['OR_TRANSIT']})
    return {'tax': round(sum(x['tax'] for x in rows), 6), 'items': rows}


def calculate_portland(gross, year=2026, filing_status='single', spouse_wages=0, *,
                       metro_resident=False, multnomah_resident=False,
                       metro_source_share=0., multnomah_source_share=0.):
    """Local taxes before any local other-jurisdiction credits; no residence guessed.

    Thresholds apply to local taxable income, not worldwide income multiplied by
    a duty-day ratio. Source deductions are allocated proportionally in this model.
    A nonresident source share is player source wages / household wages; the
    spouse is assumed to earn wages only at the shared resident location.
    """
    annual = calculate_state('OR', gross, year, filing_status, spouse_wages)
    taxable = annual['taxable_income']
    for share in (metro_source_share, multnomah_source_share):
        if not math.isfinite(share) or not 0 <= share <= 1:
            raise ValueError('Source shares must be in [0,1]')
    metro_income = taxable if metro_resident else taxable * metro_source_share
    county_income = taxable if multnomah_resident else taxable * multnomah_source_share
    metro_rules = DATA['locals']['PORTLAND_METRO_SHS']
    county_rules = DATA['locals']['MULTNOMAH_PFA']
    if filing_status == 'mfj':
        metro_rules = {**metro_rules, **metro_rules['mfj']}
        county_rules = {**county_rules, **county_rules['mfj']}
    threshold = metro_rules['threshold_2027'] if year == 2027 else metro_rules['threshold']
    first_threshold = county_rules['brackets'][1]['threshold']
    additional_threshold = county_rules['brackets'][2]['threshold']
    metro_tax = .01 * max(0., metro_income - threshold)
    county_tax = .015 * max(0., county_income - first_threshold) + .015 * max(0., county_income - additional_threshold)
    return {'tax': round(metro_tax + county_tax, 6), 'filing_status': filing_status,
            'spouse_wages': annual['spouse_wages'],
            'spouse_source_assumption': 'shared_residence;nonresident_shares_are_player_source_wages_over_household_wages' if filing_status == 'mfj' else 'not_applicable',
            'oregon_parameter_status': annual['status'], 'items': [
        {'name': 'PORTLAND_METRO_SHS', 'tax': round(metro_tax, 6), 'taxable_income': metro_income,
         'rate': .01, 'threshold': threshold, 'resident_assumed': metro_resident, 'source_ids': ['PORTLAND']},
        {'name': 'MULTNOMAH_PFA', 'tax': round(county_tax, 6), 'taxable_income': county_income,
         'first_rate': .015, 'first_threshold': first_threshold, 'additional_rate': .015,
         'additional_threshold': additional_threshold, 'resident_assumed': multnomah_resident, 'source_ids': ['PORTLAND']}
    ], 'note': 'PFA 0.8-point increase begins 2028, not 2027. Any local resident tax credits require separate review.'}


def calculate_denver_opt(monthly_denver_wages):
    """Pass iterable or mapping of actual/modeled Denver earnings per calendar month."""
    wages = monthly_denver_wages.values() if isinstance(monthly_denver_wages, dict) else monthly_denver_wages
    count = sum(_valid_amount(w) >= 500 for w in wages)
    return {'tax': round(5.75 * count, 2), 'qualifying_months': count, 'monthly_tax': 5.75,
            'source_ids': ['DENVER_OPT']}


def calculate_portland_resident_credit(local_tax, total_modified_agi, mutually_taxed_agi,
                                      other_state_actual_tax, *,
                                      other_state_allows_nonresident_credit=False,
                                      oregon_credit_claimed=True):
    """Apply separately for Metro and County, and separately for each other state.

    Portland's policy uses actual other-state tax, not a pool reduced by the
    resident's Oregon state credit. No credit for nonresident filers or reverse
    credit states. Caller limits total claims to the remaining local liability.
    """
    local_tax = _valid_amount(local_tax, 'local_tax')
    total = _valid_amount(total_modified_agi, 'total_modified_agi')
    mutual = _valid_amount(mutually_taxed_agi, 'mutually_taxed_agi')
    other = _valid_amount(other_state_actual_tax, 'other_state_actual_tax')
    if mutual > total:
        raise ValueError('Mutually taxed AGI cannot exceed total modified AGI')
    eligible = not other_state_allows_nonresident_credit and oregon_credit_claimed
    limit = local_tax * mutual / total if total else 0.
    credit = min(local_tax, limit, other) if eligible else 0.
    return {'credit': round(credit, 6), 'local_tax_limit_on_mutual_income': round(limit, 6),
            'eligible': eligible, 'source_ids': ['PORTLAND_CREDIT', 'PORTLAND_CREDIT_FORM']}


def _self_test():
    """Fixed official-table/formula examples plus household/source boundaries."""
    def close(actual, expected):
        assert math.isclose(actual, expected, abs_tol=1e-5), (actual, expected)

    # Published cumulative 2026 tax amounts; <= one cent of table rounding.
    close(round(calculate_state('CA', 774113)['ordinary_tax'], 2), 74675.27)
    close(calculate_state('WI', 333420)['tax'], 17030.62)
    close(calculate_state('OK', 14550)['tax'], 109.25)
    # CA joint $100000 taxable: $2113.48 + $14278 * 6% - $316.
    close(calculate_state('CA', 111800, filing_status='mfj')['tax'], 2654.16)
    close(calculate_state('CA', 1011800, filing_status='mfj')['surtax'], 0)
    close(calculate_state('CA', 1011900, filing_status='mfj')['surtax'], 1)
    close(calculate_state('CA', 504411, filing_status='mfj')['personal_credit'], 316)
    close(calculate_state('CA', 504412, filing_status='mfj')['personal_credit'], 304)
    close(calculate_nonresident('CA', 50_000_000, .015, filing_status='mfj')['surtax'], 0)
    # Colorado household AGI threshold stays $300000 for joint filers.
    close(calculate_state('CO', 300000, filing_status='mfj')['tax'], 11783.2)
    close(calculate_state('CO', 300001, filing_status='mfj')['tax'], 13112.044)
    close(calculate_state('IL', 500000, filing_status='mfj')['personal_exemption'], 5850)
    close(calculate_state('IL', 500001, filing_status='mfj')['personal_exemption'], 0)
    close(calculate_state('AZ', 100000, filing_status='mfj')['tax'], 1695)
    close(calculate_state('LA', 100000, filing_status='mfj')['tax'], 2227.5)
    close(calculate_state('OK', 29100, filing_status='mfj')['tax'], 218.5)
    close(calculate_state('UT', 50000, filing_status='mfj')['tax'], 469.462)
    # Oregon joint federal subtraction is $7640 at wages $100000, not Single tax.
    close(calculate_state('OR', 100000, filing_status='mfj')['deduction'], 13460)
    close(calculate_state('OR', 250000, filing_status='mfj')['deduction'], 12820)
    close(calculate_state('OR', 290000, filing_status='mfj')['deduction'], 5820)
    close(calculate_nonresident('OR', 1000000, .01)['tax'], 582.03575)
    # MN: independently compute two single taxes on $84700 each.
    close(calculate_state('MN', 200000, filing_status='mfj')['tax'], 10813.05)
    mn = calculate_state('MN', 200000, filing_status='mfj', spouse_wages=100000)
    close(mn['tax'], 10553.21)
    close(mn['marriage_credit'], 259.84)
    close(calculate_state('MN', 300000, filing_status='mfj')['deduction'], 28932)
    close(calculate_state('MN', 10_000_000, filing_status='mfj')['deduction'], 6120)
    wi_one = calculate_state('WI', 100000, filing_status='mfj')
    wi_two = calculate_state('WI', 100000, filing_status='mfj', spouse_wages=50000)
    close(wi_one['deduction'], 11805.5312)
    close(wi_one['tax'] - wi_two['tax'], 480)
    wi_nr = calculate_nonresident('WI', 1000000, .01, filing_status='mfj', spouse_wages=500000)
    close(wi_nr['marriage_credit'], 0)
    close(wi_nr['tax'], 651.62905)
    # $500000 joint Oregon taxable income: SHS $2950 + PFA $6000.
    for year, expected in ((2026, 8950), (2027, 8890)):
        close(calculate_portland(505820, year, 'mfj', metro_resident=True,
                                 multnomah_resident=True)['tax'], expected)
    close(calculate_portland(505820, filing_status='mfj', metro_source_share=.1,
                             multnomah_source_share=.1)['tax'], 0)
    close(calculate_payroll('CA', 1_000_000)['tax'], 13000)
    close(calculate_payroll('OR', 1_000_000)['tax'], 2107)
    close(calculate_payroll('MN', 1_000_000)['tax'], 811.8)
    for code in STATES:
        for status in ('single', 'mfj'):
            close(calculate_state(code, 0, filing_status=status)['tax'], 0)
            for gross in (1000, 20000, 80000, 200000, 10_000_000):
                spouse = gross / 2 if status == 'mfj' else 0
                result = calculate_state(code, gross, filing_status=status, spouse_wages=spouse)
                assert 0 <= result['tax'] <= gross
                close(calculate_nonresident(code, gross, 0, filing_status=status,
                                            spouse_wages=spouse)['tax'], 0)
                # At share=1, omit spouse wages to keep the work-state model
                # consistent with its zero spouse-source-income assumption.
                close(calculate_nonresident(code, gross, 1, filing_status=status)['tax'],
                      calculate_state(code, gross, filing_status=status)['tax'])
    assert 'proxy' in calculate_state('MN', 10000, filing_status='mfj')['scope_status']
    for kwargs in ({'filing_status': 'mfs'}, {'spouse_wages': 1},
                   {'filing_status': 'mfj', 'spouse_wages': 100001},
                   {'filing_status': 'mfj', 'spouse_wages': float('nan')},
                   {'filing_status': 'mfj', 'spouse_wages': -1}):
        try:
            calculate_state('CA', 100000, **kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError(('Invalid household accepted', kwargs))
    print('Western state Single/MFJ numeric and source-allocation checks passed.')


if __name__ == '__main__':
    _self_test()
