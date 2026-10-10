"""Fail closed on inconsistent money; annotate independently uncertain facts."""
import math
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]

def check(row):
    fields=['spotrac_salary_usd','gross_usd','estimated_tax_usd','estimated_net_usd']
    for key in fields:
        if not isinstance(row.get(key),(int,float)) or not math.isfinite(row[key]):
            raise ValueError('data_invalid: 非有效金额 '+key)
    components=row.get('components_usd')
    if not isinstance(components,dict) or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in components.values()):
        raise ValueError('data_invalid: 税项明细缺失或无效')
    if abs(sum(components.values())-row['estimated_tax_usd'])>.25:
        raise ValueError('data_invalid: 税项合计与总税额不符，停止发布数字')
    if abs(row['gross_usd']-row['estimated_tax_usd']-row['estimated_net_usd'])>.25:
        raise ValueError('data_invalid: 税前调整、总税额与税后金额不符')
    gross=row['spotrac_salary_usd']-row['cashflow_scenario']['modeled_final_reduction_usd']+row.get('extra_settlement_bonus_usd',0)+row.get('extra_cup_bonus_usd',0)
    if abs(gross-row['gross_usd'])>.25:
        raise ValueError('data_invalid: 收入调整不符，停止发布数字')
    tax_state=row.get('team_tax_context',{}).get('team_state')
    residence=row.get('residence_scenario',{})
    # A differing residence is allowed when explicitly supplied; never equate trade with residency.
    issues=[]
    c=row.get('contract_context',{})
    if c.get('status')=='conflict':issues.append('合同标签冲突：不展示未经确认的当前合同规模；薪资仍来自独立Cash数据。')
    elif c.get('status')!='verified':issues.append('当前合同规模尚未核实。')
    if not row.get('sources',{}).get('salary'):raise ValueError('data_invalid: 缺少薪资来源')
    if not row.get('team') or not residence:raise ValueError('data_invalid: 球队或居民情景缺失')
    return {'money_reconciled':True,'contract_status':c.get('status','unverified'),'warnings':issues,
            'scope':'算术与字段一致性检查通过，不等于源数据真实性或私人税单已核实'}

def metadata():
    edition=json.loads((ROOT/'EDITION.json').read_text()) if (ROOT/'EDITION.json').is_file() else {'version':'未标记（导入暂存或非发行版）'}
    return {'skill_version':edition['version'],'generated_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'time_zone':'Asia/Shanghai'}
