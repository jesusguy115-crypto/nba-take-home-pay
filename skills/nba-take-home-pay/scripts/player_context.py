"""Presentation-only contract facts; never feed totals or AAV into tax inputs."""
from functools import lru_cache
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

@lru_cache(maxsize=1)
def contracts():
    path = ROOT / 'assets/player-contracts-2026-27.json'
    return json.loads(path.read_text(encoding='utf-8')).get('players', {}) if path.is_file() else {}

def season(year):
    return str(year) + '–' + str(year + 1)[-2:] if year is not None else '未核实'

def amount(value):
    return format(value / 10000, ',.2f') + '万美元' if value is not None else '未披露/未核实'

def describe(record):
    years = str(record['years']) + '年' if record.get('years') is not None else '年限未核实'
    span = season(record.get('start_year')) + '至' + season(record.get('end_year'))
    return (years + ' / ' + amount(record.get('total_usd')) + '；保障' + amount(record.get('guaranteed_usd'))
            + '；平均年薪' + amount(record.get('average_salary_usd')) + '；' + span)

def context(player_id, active=True):
    record = contracts().get(str(player_id), {})
    current = record.get('current', [])
    extensions = record.get('extensions', [])
    current_text = ' / '.join(describe(c) for c in current) if current else ('当前合同尚未核实' if active else '非现役保留付款；执行中合同未核实')
    extension_text = ' / '.join(describe(c) for c in extensions) if extensions else ('页面未列未来续约' if record.get('status') == 'verified' else '续约情况尚未核实')
    return dict(record, current=current, extensions=extensions, current_summary=current_text,
                extension_summary=extension_text, status=record.get('status', 'unverified'))

def enrich(result):
    result['contract_context'] = context(result['player_id'], result.get('active_roster', True))
    return result
