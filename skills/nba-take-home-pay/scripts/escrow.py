"""Explicit league-settlement assumptions, separate from final taxes and cash timing."""
import json
import math
from pathlib import Path

RULES = json.loads(Path(__file__).with_name('escrow-rules.json').read_text(encoding='utf-8'))
SCENARIO_KEYS = {'final_reduction_rate', 'withholding_rate',
                 'prior_season_final_reduction_rate', 'escrow_rate', 'settlement_bonus_usd'}
SNAPSHOT_FIELDS = ('estimated_net_usd', 'rounded_net_usd', 'estimated_tax_usd',
                   'effective_tax_rate', 'components_usd', 'gross_usd', 'contract_gross_usd',
                   'filing_scenario', 'specific_uncertainties', 'escrow_scenario',
                   'cashflow_scenario', 'previous_season_adjusted_gross_usd',
                   'calculation_type', 'settlement_impact', 'extra_settlement_bonus_usd')


def rate(value, name):
    if isinstance(value, bool):
        raise ValueError(name + ' must be numeric, not boolean')
    value = float(value)
    if not math.isfinite(value) or not 0 <= value <= .10:
        raise ValueError(name + ' must be finite and between 0 and 0.10')
    return value


def selection(scenario):
    """The legacy escrow_rate controls only initial withholding, never final loss."""
    legacy = scenario.get('escrow_rate')
    withholding = scenario.get('withholding_rate')
    if legacy is not None and withholding is not None and float(legacy) != float(withholding):
        raise ValueError('escrow_rate and withholding_rate conflict; use withholding_rate for initial withholding')
    selected = {
        'withholding_rate': rate(withholding if withholding is not None else
                                legacy if legacy is not None else RULES['default_withholding_rate'],
                                'withholding_rate'),
        'final_reduction_rate': rate(scenario.get('final_reduction_rate', RULES['default_final_reduction_rate']),
                                    'final_reduction_rate'),
        'prior_season_final_reduction_rate': rate(scenario.get('prior_season_final_reduction_rate',
                                                    RULES['default_prior_season_final_reduction_rate']),
                                                'prior_season_final_reduction_rate'),
    }
    supplemental = scenario.get('settlement_bonus_usd', 0)
    if isinstance(supplemental, bool) or not math.isfinite(float(supplemental)) or float(supplemental) < 0:
        raise ValueError('settlement_bonus_usd must be finite and nonnegative')
    selected['settlement_bonus_usd'] = float(supplemental)
    selected.update({
        'label': ('不计本赛季联盟结算调整的税后基准' if selected['final_reduction_rate'] == 0 and not selected['settlement_bonus_usd'] else
                  f'按{selected["final_reduction_rate"]:.2%}历史扣减比例参照的税后情景（非本赛季已知结算）' if 'final_reduction_rate' not in scenario else
                  f'最终工资扣减{selected["final_reduction_rate"]:.2%}的自定义税后情景'),
        'selection_reason': ('user_supplied_final_reduction_assumption' if 'final_reduction_rate' in scenario else
                             'historical_2025_26_reference_not_current_season_forecast'),
        'supplemental_payment_status': 'user_supplied_assumption' if 'settlement_bonus_usd' in scenario else 'unknown_default_zero',
        'supplemental_allocation_policy': 'same_contract_service_mix_and_24_payment_year_attribution_proxy_not_actual_payment_timing',
        'current_season_rate_status': 'unknown_assumption',
        'actual_2026_27_rate_known': False,
        'historical_reference_season': RULES['historical_reference_season'],
        'historical_reference_status': RULES['historical_reference_status'],
        'prior_season_rate_status': ('user_supplied_assumption' if 'prior_season_final_reduction_rate' in scenario else
                                     'reported_aggregate_reference_not_individual_payroll_verified'),
        'tax_timing_policy': RULES['tax_timing_policy'],
        'withholding_scope': 'Spotrac_contract_cash_proxy_excludes_separately_supplied_Cup_bonus',
        'legacy_escrow_rate_used': legacy is not None,
        'sources': RULES['sources'],
    })
    return selected


def cashflow(salary, bonus, selected):
    """Before-tax components only: original salary minus loss equals settled wages."""
    held = salary * selected['withholding_rate']
    loss = salary * selected['final_reduction_rate']
    supplemental = selected['settlement_bonus_usd']
    return {
        'temporary_escrow_usd': round(held, 2),
        'initial_before_tax_payable_usd': round(salary + bonus - held, 2),
        'modeled_final_reduction_usd': round(loss, 2),
        'modeled_refund_before_tax_usd': round(max(0, held - loss), 2),
        'modeled_additional_collection_before_tax_usd': round(max(0, loss - held), 2),
        'supplemental_settlement_payment_before_tax_usd': round(supplemental, 2),
        'settled_before_tax_gross_usd': round(salary + bonus - loss + supplemental, 2),
        'actual_net_payroll_deposit_usd': None,
        'actual_settlement_payment_date': None,
        'note': '暂扣、返还和补扣均为税前分解，最终扣减只计算一次；未估算实际工资预扣或银行到账。返还时点及税务处理未知。',
    }
