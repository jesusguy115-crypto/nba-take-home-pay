"""Presentation metadata for NBA-team states; never changes tax calculations."""
from duty_days import home_location

NO_STATE_INCOME_TAX={'TX':'得克萨斯州','FL':'佛罗里达州','TN':'田纳西州'}

def add_state_label(result):
    location=home_location(result['team'])
    state=location['state']
    exempt=location['country']=='US' and state in NO_STATE_INCOME_TAX
    residence=result['residence_scenario']
    result['team_tax_context']={
        'team_state':state,
        'team_state_zh':NO_STATE_INCOME_TAX.get(state),
        'team_in_no_state_income_tax_state':exempt,
        'badge':'免税州（无州个人所得税）' if exempt else None,
        'display_team':f"{result['team_zh']}｜{NO_STATE_INCOME_TAX[state]}（免税州）" if exempt else result['team_zh'],
        'residence_scenario_has_no_state_income_tax':residence['country']=='US' and residence['state'] in NO_STATE_INCOME_TAX,
        'scope_note':'标签指球队所在州，不确认球员真实税籍；仍计算联邦税、雇员工资税和适用的客场州/地方税。',
    }
    return result
