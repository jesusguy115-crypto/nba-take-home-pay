"""Single/MFJ, wages-only state tax scenarios researched 2026-10-09.
Not a return preparer; nonresident allocation approximations are explicit.
Income-tax gross is household wages, including spouse_wages. Payroll is personal.
Load tax-east.json beside this module. No network or dependencies.
"""
import json
import math
from pathlib import Path

DATA = json.loads(Path(__file__).with_name('tax-east.json').read_text())
STATES = DATA['jurisdictions']
LOCALS = DATA['locals']
RECIPROCAL = DATA['reciprocity']


def progressive(income, brackets):
    rows = []
    for i, b in enumerate(brackets):
        lo = b['threshold']
        hi = brackets[i + 1]['threshold'] if i + 1 < len(brackets) else None
        amount = max(0.0, min(income, hi if hi is not None else income) - lo)
        if amount:
            rows.append({'lower': lo, 'upper': hi, 'rate': b['rate'],
                         'income': amount, 'tax': amount * b['rate']})
    return sum(r['tax'] for r in rows), rows


def _validate_gross(gross):
    gross = float(gross)
    if not math.isfinite(gross) or gross < 0:
        raise ValueError('gross must be a finite nonnegative amount')
    return gross


def _fica(gross):
    return min(gross, 184500) * .062 + gross * .0145 + max(0, gross - 200000) * .009


def _household(gross, filing_status, spouse_wages):
    gross = _validate_gross(gross)
    filing_status = str(filing_status).lower()
    if filing_status not in ('single', 'mfj'):
        raise ValueError('filing_status must be single or mfj; MFS is not Single')
    spouse_wages = _validate_gross(spouse_wages)
    if spouse_wages > gross:
        raise ValueError('spouse_wages must be included in and no greater than gross')
    if filing_status == 'single' and spouse_wages:
        raise ValueError('single filing_status requires spouse_wages=0')
    return gross, filing_status, spouse_wages


def _validate_year(year):
    if year not in (2026, 2027):
        raise ValueError('Only scenario years 2026 and 2027 are supported')


def _ny_recapture(gross, taxable, ordinary_tax, filing_status, year):
    params = STATES['NY']['recapture_by_filing_status'][filing_status][str(year)]
    fraction = 0.0
    if gross > 25000000:
        tax = taxable * .109
        rule = 'full_10.9_percent'
    elif taxable <= params['first_band_upper']:
        fraction = round(min(1.0, (gross - 107650) / 50000), 4)
        if 'first_band_target_rate' in params:
            benefit = taxable * params['first_band_target_rate'] - ordinary_tax
        else:
            benefit = params['first_band_increment']
        tax = ordinary_tax + benefit * fraction
        rule = 'first_band_recapture'
    else:
        for upper, base, increment, agi_threshold in params['bands']:
            if taxable <= upper:
                fraction = round(min(1.0, max(0, gross - agi_threshold) / 50000), 4)
                tax = ordinary_tax + base + increment * fraction
                rule = f'recapture_band_up_to_{upper}'
                break
    return tax, {'name': 'New York benefit recapture', 'tax': tax - ordinary_tax,
                 'formula': rule, 'phase_in_fraction': fraction,
                 'filing_status': filing_status, 'parameter_year': year}


def calculate_state(code, gross, year=2026, filing_status='single', spouse_wages=0):
    code = code.upper()
    gross, filing_status, spouse_wages = _household(gross, filing_status, spouse_wages)
    _validate_year(year)
    p = STATES[code]
    params = p['filing_status_parameters'][filing_status]
    deduction = min(gross, params['deduction'])
    exemption = min(gross - deduction, params['exemption_amount'])
    status = p['status']
    adjustments = []
    limitations = []
    if filing_status == 'mfj':
        limitations.append('Wages-only joint-return scenario with shared modeled residency, no dependents, and no separate-return election; spouse wages are included in gross. Zero spouse wages is a comparison assumption only.')
    brackets = [dict(b) for b in params['brackets']]
    if year == 2027:
        status = '2026_parameters_proxy_for_2027'
        if code == 'NY':
            for b, rate in zip(brackets, p['enacted_2027_first_five_rates']):
                b['rate'] = rate
            status = '2027_enacted_rates_and_recapture_other_2026_parameters'
        elif code in ('IN', 'NC'):
            brackets[0]['rate'] = p['enacted_2027_rate']
            status = '2027_enacted_rate_other_2026_parameters'
        elif code in ('FL', 'TN', 'PA'):
            status = 'continuing_statutory_rate'
    if code == 'OH':
        exemption = 0 if gross >= 500000 else (2400 if gross <= 40000 else 2150 if gross <= 80000 else 1900)
        exemption = min(gross, exemption * (2 if filing_status == 'mfj' else 1))
        if gross < 500000:
            status += ';2025_indexed_exemption_proxy'
            limitations.append('Ohio indexed personal exemptions use 2025 amounts; other low-income and family credits are not comprehensively modeled.')
    if code == 'MA':
        deduction = min(gross, min(2000.0, _fica(gross - spouse_wages))
                        + min(2000.0, _fica(spouse_wages)))
        exemption = min(max(0, gross - deduction), params['exemption_amount'])
    taxable = max(0.0, gross - deduction - exemption)
    tax, rows = progressive(taxable, brackets)
    if code == 'OH' and taxable > 26050:
        adjustments.append({'name': 'Ohio statutory base amount at threshold', 'tax': 332.0,
                            'formula': '$332 + 2.75% of taxable income exceeding $26,050'})
        tax += 332.0
    if code == 'NY' and gross > 107650:
        tax, recapture = _ny_recapture(gross, taxable, tax, filing_status, year)
        adjustments.append(recapture)
    if code == 'OH' and filing_status == 'mfj':
        credit_params = p['joint_credit']
        qualifies = (spouse_wages >= credit_params['minimum_wages_each_spouse']
                     and gross - spouse_wages >= credit_params['minimum_wages_each_spouse']
                     and gross < credit_params['magi_must_be_less_than'])
        rate = next(r['rate'] for r in credit_params['rates']
                    if r['upper'] is None or taxable <= r['upper'])
        credit = min(tax, credit_params['cap'], tax * rate) if qualifies else 0.0
        tax -= credit
        adjustments.append({'name': 'Ohio joint filing credit', 'tax': -credit,
                            'eligible': qualifies, 'rate': rate, 'cap': 650,
                            'minimum_wages_each_spouse': 500,
                            'household_magi_must_be_less_than': 500000,
                            'formula': 'min(650, tax_before_credit * rate) if both spouses earn >=500 and household MAGI<500000 else 0'})
    if code == 'MA':
        surtax = max(0.0, taxable - 1107750) * .04
        tax += surtax
        adjustments.append({'name': 'Massachusetts 4% surtax', 'tax': surtax,
                            'threshold': 1107750, 'rate': .04,
                            'formula': '0.04 * max(0, taxable_income - 1107750)'})
    return {'code': code, 'year': year, 'tax': max(0.0, tax),
            'gross': gross, 'taxable_income': taxable,
            'filing_status': filing_status, 'spouse_wages': spouse_wages,
            'taxpayer_wages': gross - spouse_wages, 'gross_basis': 'household_wages',
            'deduction': deduction, 'exemption': exemption,
            'brackets': rows, 'adjustments': adjustments,
            'status': status, 'source_ids': p['source_ids'], 'limitations': limitations}


def source_tax(code, gross, ratio, year=2026, resident_state=None,
               filing_status='single', spouse_wages=0):
    """Source state tax before credits. MA uses source-only surtax threshold.
    Remaining states use explicitly approximate proportional full-income tax.
    ratio is source wages / household gross, not the player's duty-day ratio.
    Source wages belong to the player; spouse wages are in the resident state.
    Residence-state caller must use calculate_state instead of this function.
    """
    code = code.upper()
    gross, filing_status, spouse_wages = _household(gross, filing_status, spouse_wages)
    ratio = float(ratio)
    if not math.isfinite(ratio) or not 0 <= ratio <= 1:
        raise ValueError('ratio must be between 0 and 1')
    p = STATES[code]
    if gross * ratio > gross - spouse_wages + 1e-8:
        raise ValueError('source wages exceed taxpayer wages; this model assumes no spouse away-state wages')
    base = calculate_state(code, gross, year, filing_status, spouse_wages)
    base.update({'source_ratio': ratio, 'source_income': gross * ratio,
                 'resident_state': resident_state})
    if filing_status == 'mfj':
        base['limitations'].append('Source ratio uses household wages as denominator and assumes spouse wages have no away-state source; mixed-residency and state separate-return requirements need separate review.')
    if code == 'DC' or (resident_state and resident_state.upper() in RECIPROCAL.get(code, [])):
        base.update({'tax': 0.0, 'taxable_income': 0.0, 'brackets': [],
                     'deduction': 0.0, 'exemption': 0.0,
                     'adjustments': [{'name': 'DC nonresident wage exemption' if code == 'DC' else 'Reciprocal wage exemption', 'tax': 0.0}],
                     'allocation_method': 'exempt_nonresident_wages'})
        return base
    if code == 'MA':
        # FICA deduction attributable to MA wages, capped at $2,000; total FICA is
        # prorated by modeled source share because actual withholding timeline is unknown.
        taxpayer_wages = gross - spouse_wages
        taxpayer_source_ratio = gross * ratio / taxpayer_wages if taxpayer_wages else 0.0
        deduction = min(gross * ratio, min(2000.0, _fica(taxpayer_wages) * taxpayer_source_ratio))
        exemption_amount = p['filing_status_parameters'][filing_status]['exemption_amount']
        exemption = min(max(0.0, gross * ratio - deduction), exemption_amount * ratio)
        taxable = max(0.0, gross * ratio - deduction - exemption)
        tax, rows = progressive(taxable, p['brackets'])
        surtax = max(0.0, taxable - 1107750) * .04
        base.update({'tax': tax + surtax, 'taxable_income': taxable,
                     'deduction': deduction, 'exemption': exemption, 'brackets': rows,
                     'adjustments': [{'name': 'MA surtax on MA-source income only', 'tax': surtax,
                                      'threshold': 1107750, 'rate': .04}],
                     'allocation_method': 'source_income_tax_with_prorated_exemption_and_full_surtax_threshold',
                     'source_ids': p['source_ids'] + ['ma-nonresident', 'ma-surtax-law'],
                     'limitations': base['limitations'] + ['MA-attributable player FICA deduction uses the player source share, not the household share; spouse has no MA-source wages. Actual payroll timing may differ.',
                                     'MFJ uses one shared surtax threshold and prorates the joint exemption by household MA-source wages; mixed residency and mandatory separate-return exceptions are not modeled.']})
        return base
    whole_tax = base['tax']
    base['tax'] *= ratio
    for key in ('deduction', 'exemption', 'taxable_income'):
        base[key] *= ratio
    base['full_income_tax_before_allocation'] = whole_tax
    base['allocation_method'] = 'scenario_full_income_tax_times_source_ratio'
    base['brackets'] = [{**r, 'tax': r['tax'] * ratio,
                         'income': r['income'] * ratio} for r in base['brackets']]
    base['adjustments'] = [{**r, 'tax': r['tax'] * ratio} for r in base['adjustments']]
    return base


def calculate_local(code, gross, resident=False, ratio=1.0, year=2026, pay_date=None,
                    filing_status='single', spouse_wages=0):
    """City/county tax before intercity credit; not added by calculate_state.
    Philadelphia rate defaults to the season's Jul2026-Jun2027 rate;
    use pay_date for actual calendar-year payment modeling.
    """
    code = code.upper()
    p = LOCALS[code]
    gross, filing_status, spouse_wages = _household(gross, filing_status, spouse_wages)
    _validate_year(year)
    ratio = float(ratio)
    if not math.isfinite(ratio) or not 0 <= ratio <= 1:
        raise ValueError('ratio must be between 0 and 1')
    params = p['filing_status_parameters'][filing_status]
    taxable = gross if resident else gross * ratio
    deduction = params['deduction'] if resident else params['nonresident_deduction']
    taxable = max(0.0, taxable - deduction)
    if code == 'NYC':
        tax, rows = progressive(taxable, params['brackets']) if resident else (0.0, [])
    else:
        rate = p['resident_rate'] if resident else p['nonresident_rate']
        if code == 'PHI' and pay_date:
            if pay_date < '2026-07-01':
                rate = .0374 if resident else .0343
            elif pay_date >= '2027-07-01':
                rate = .03730 if resident else .03420
        tax = taxable * rate
        rows = [{'lower': 0, 'upper': None, 'rate': rate, 'income': taxable, 'tax': tax}]
    return {'code': code, 'year': year, 'tax': tax, 'taxable_income': taxable, 'deduction': deduction,
            'gross': gross, 'gross_basis': 'household_wages',
            'filing_status': filing_status, 'spouse_wages': spouse_wages,
            'resident': resident, 'source_ratio': 1 if resident else ratio,
            'brackets': rows, 'source_ids': p['source_ids'],
            'limitations': (['Both spouses share the modeled local residency; mixed-residency returns and low-income/family relief programs are not modeled.']
                            if filing_status == 'mfj' else []),
            'status': p['status']}


def local_credit_limit(code, mutually_taxed_income):
    p = LOCALS[code]
    return max(0.0, mutually_taxed_income) * p['other_local_credit_limit_rate']


def employee_payroll(code, gross, year=2026):
    """Home-employment payroll scenario only. Do NOT apply to every away-state day.
    Private equivalent plans/employer-paid shares can alter these deductions.
    """
    p = STATES[code.upper()]
    rows = []
    for x in p.get('payroll', []):
        taxable = min(gross, x.get('wage_cap') or gross)
        tax = taxable * x['rate']
        if x.get('tax_cap') is not None:
            tax = min(tax, x['tax_cap'])
        rows.append({**x, 'tax': max(0.0, tax), 'taxable_income': taxable,
                     'year': year, 'status': '2026_parameter' if year == 2026 else '2026_proxy_for_2027'})
    return rows
