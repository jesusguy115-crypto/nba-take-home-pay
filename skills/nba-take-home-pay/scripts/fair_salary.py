"""DARKO Fair Salary: independent valuation overlay, never a tax input.

The full third-party snapshot lives in a local .cache, not in release assets.
"""
import argparse
from datetime import datetime, timezone
from functools import lru_cache
import json
import math
import os
from pathlib import Path
import re
import unicodedata
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'https://beta.darko.app/'
METHOD = 'https://beta.darko.app/about/fair-salary'
NOTICE = ('合理薪资来自 DARKO Fair Salary，是场上贡献的年薪估值，不是税后收入或合同报价；'
          '保留来源计价口径，不与不同赛季的合同工资直接计算溢价。')


def cache_path():
    return Path(os.environ.get('NBA_FAIR_SALARY_CACHE', str(ROOT / '.cache/fair-salary.json'))).expanduser()


def name_key(name):
    name = unicodedata.normalize('NFKD', str(name))
    return ''.join(c.lower() for c in name if c.isalnum() and not unicodedata.combining(c))


def js_array(text, start):
    """Decode a data-only JS array; never execute source JavaScript."""
    depth, quoted, escaped = 0, False, False
    for end in range(start, len(text)):
        c = text[end]
        if quoted:
            if escaped: escaped = False
            elif c == '\\': escaped = True
            elif c == '"': quoted = False
        elif c == '"': quoted = True
        elif c == '[': depth += 1
        elif c == ']':
            depth -= 1
            if depth == 0: break
    else: raise ValueError('DARKO数据数组不完整')
    raw = text[start:end+1]
    chunks = re.split(r'("(?:\\.|[^"\\])*")', raw)
    for i in range(0, len(chunks), 2):
        chunks[i] = re.sub(r'(?<=[,\[])\s*(-?)\.(\d)', r'\g<1>0.\2', chunks[i])
        chunks[i] = re.sub(r'\b(?:undefined|NaN)\b', 'null', chunks[i])
    return json.loads(''.join(chunks))


def parse_snapshot(page):
    match = re.search(r'players:\{keys:\s*(\[)', page)
    if not match: raise ValueError('DARKO页面结构已变化，找不到球员数据')
    keys = js_array(page, match.start(1))
    values_start = re.search(r'values:\s*(\[)', page[match.end():])
    if not values_start: raise ValueError('DARKO页面缺少数值数组')
    columns = js_array(page, match.end() + values_start.start(1))
    if len(keys) != len(columns) or len(set(map(len, columns))) != 1:
        raise ValueError('DARKO列长度不一致')
    for key in ('nba_id', 'player_name', 'sal_market_fixed', 'season'):
        if key not in keys: raise ValueError('DARKO缺少字段：' + key)
    date = re.search(r'ratingsThrough:\s*"(\d{4}-\d{2}-\d{2})"', page)
    if not date: raise ValueError('DARKO缺少比赛数据截止日期')
    players = []
    for values in zip(*columns):
        r = dict(zip(keys, values)); value = r['sal_market_fixed']
        if value is None: continue
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
            raise ValueError('DARKO合理薪资不是有限数字')
        players.append({'nba_id': str(r['nba_id']), 'name': r['player_name'],
                        'value_usd': value, 'source_season_end': r['season']})
    if not players or len({r['nba_id'] for r in players}) != len(players):
        raise ValueError('DARKO球员列表为空或存在重复ID')
    return {'schema_version': 1, 'provider': 'DARKO', 'source_url': SOURCE,
            'method_url': METHOD, 'ratings_through': date.group(1),
            'fetched_at': datetime.now(timezone.utc).isoformat(),
            'valuation_currency_basis': '2025-26工资帽美元（DARKO原生口径）',
            'notice': NOTICE, 'players': players}


def refresh(path=None, timeout=4):
    path = Path(path or cache_path())
    req = urllib.request.Request(SOURCE, headers={'User-Agent': 'NBA-Take-Home-Pay/0.9.6 (Fair Salary query)'})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read(10_000_001)
    if len(raw) > 10_000_000: raise ValueError('DARKO页面超过安全读取大小')
    snapshot = parse_snapshot(raw.decode('utf-8'))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(snapshot, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    tmp.replace(path)
    load_snapshot.cache_clear()
    return snapshot


@lru_cache(maxsize=4)
def load_snapshot(path_string, offline=False):
    path = Path(path_string)
    try:
        snapshot = json.loads(path.read_text(encoding='utf-8'))
        if snapshot.get('schema_version') != 1 or not isinstance(snapshot.get('players'), list):
            raise ValueError('合理薪资缓存格式不兼容')
        return snapshot, None
    except (OSError, ValueError) as error:
        if not offline:
            try: return refresh(path, timeout=3), None
            except Exception as fetch_error: error = fetch_error
        return None, str(error)


def enrich(row, snapshot=None):
    error = None
    if snapshot is None:
        snapshot, error = load_snapshot(str(cache_path()), os.environ.get('NBA_FAIR_SALARY_OFFLINE') == '1')
    info = {'label': '合理薪资', 'provider': 'DARKO', 'source_url': SOURCE,
            'method_url': METHOD, 'status': 'unavailable', 'value_usd': None,
            'rounded_value_usd': None, 'notice': NOTICE}
    if snapshot is None:
        info['reason'] = 'DARKO缓存缺失或无法读取；可运行 fair_salary.py --refresh。'
        info['error'] = error
    else:
        info.update({k: snapshot.get(k) for k in ('ratings_through', 'fetched_at', 'valuation_currency_basis')})
        matches = [p for p in snapshot['players'] if name_key(p['name']) == name_key(row['player'])]
        if len(matches) == 1:
            p = matches[0]; value = p.get('value_usd')
            if isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value):
                info.update(status='available', value_usd=value,
                            rounded_value_usd=round(value / 10000) * 10000, nba_id=p['nba_id'],
                            global_rank=1+sum(x['value_usd'] > value for x in snapshot['players']),
                            rank_population=len(snapshot['players']), rank_scope='DARKO完整估值快照')
        if info['status'] != 'available':
            info['reason'] = 'DARKO当前快照未唯一匹配；不代表球员价值为零。'
    row['fair_salary'] = info
    return row


def footer(infos):
    dates = sorted({str(i['ratings_through']) for i in infos if i.get('ratings_through')})
    bases = sorted({str(i['valuation_currency_basis']) for i in infos if i.get('valuation_currency_basis')})
    return ('合理薪资来源：DARKO Fair Salary；比赛数据截至' + ('、'.join(dates) or '未取得') +
            '；' + ('、'.join(bases) or '原生美元口径') + '。场上贡献估值，非税后收入或合同报价；不同计价赛季不直接计算溢价。')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--refresh', action='store_true', help='下载公开页面并更新本机合理薪资缓存')
    p.add_argument('--output', type=Path, help='本机缓存位置，不放入发行包')
    a = p.parse_args()
    try:
        snap = refresh(a.output) if a.refresh else load_snapshot(str(a.output or cache_path()), True)[0]
        print(json.dumps({'status': 'available' if snap else 'unavailable',
                          'ratings_through': (snap or {}).get('ratings_through'),
                          'players': len((snap or {}).get('players', [])), 'cache': str(a.output or cache_path())}, ensure_ascii=False))
    except Exception as e:
        p.exit(2, '合理薪资更新失败，税后计算仍可使用：' + str(e) + '\n')
if __name__ == '__main__': main()
