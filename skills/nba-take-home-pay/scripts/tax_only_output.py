"""Public result schema for contract wages minus estimated taxes."""
REMOVED={'escrow_scenario','cashflow_scenario','contract_baseline','settlement_impact','extra_settlement_bonus_usd','previous_season_adjusted_gross_usd','contract_baseline_note','settlement_rules','settlement_policy','settlement','settlement_note','darko_value'}
def clean(value):
    if isinstance(value,dict):
        return {k:clean(v) for k,v in value.items() if k not in REMOVED}
    if isinstance(value,list):return [clean(v) for v in value]
    return value

SNAPSHOT_FIELDS=('estimated_net_usd','rounded_net_usd','estimated_tax_usd','effective_tax_rate','components_usd','gross_usd','contract_gross_usd','filing_scenario','specific_uncertainties','calculation_type')
