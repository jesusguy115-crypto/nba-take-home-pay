"""Render one query result as a portable, offline chart and matching table."""
import argparse
from copy import deepcopy
import base64
import html
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STYLE_VERSION = 'courtside-ledger-2'
FILING = {'single': 'Single工资情景', 'mfj': '夫妻合报工资情景', 'individual_canada': '加拿大个人申报'}


def money(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Chart amount must be a finite number')
    return value


def safe_url(value):
    return value if isinstance(value, str) and value.startswith('https://') else ''


def display(value, decimals=0):
    return format(value / 10000, ',.' + str(decimals) + 'f')


def chart_data(payload):
    names = json.loads((ROOT / 'assets/player-name-index-2026-27.json').read_text(encoding='utf-8'))
    names = {r['player_id']: r.get('chinese_name') or r['english_name'] for r in names['players']}
    records = payload.get('results', [payload])
    if payload.get('status') or not isinstance(records, list):
        raise ValueError('Chart requires a successful query result')
    query = payload.get('query', {})
    af = query.get('age_filter') or {}
    scope = []
    if af.get('birth_year_min') is not None or af.get('birth_year_max') is not None:
        lo, hi = af.get('birth_year_min'), af.get('birth_year_max')
        scope.append('00后' if (lo, hi) == (2000, 2009) else '90后' if (lo, hi) == (1990, 1999)
                     else f'{lo or "不限"}—{hi or "不限"}年出生')
    lower, upper, under = af.get('min_inclusive'), af.get('max_inclusive'), af.get('max_exclusive')
    if lower is not None and upper is not None:
        scope.append(f'{lower}至{upper}岁')
    elif lower is not None:
        scope.append(f'{lower}岁及以上')
    elif upper is not None:
        scope.append(f'{upper}岁以内')
    if under is not None:
        scope.append(f'未满{under}岁')
    if query.get('team'):
        from duty_days import TEAMS
        scope.insert(0, TEAMS[query['team']][0])
    season = payload.get('season', '2026-27')
    basis = query.get('sort', 'net')
    order = query.get('order', 'desc' if basis != 'input' else 'input')
    metric = 'gross' if basis == 'gross' else 'baseline' if query.get('settlement') == 'baseline' else 'net'
    initial_label = '税前薪水' if metric == 'gross' else '零调整税后薪水' if metric == 'baseline' else '税后薪水'
    player_labels = [names.get(r['player_id'], r['player']) for r in records]
    if query.get('kind') == 'comparison':
        subject = '、'.join(player_labels[:3])
        if len(player_labels) > 3:
            subject += f'等{len(player_labels)}名球员'
        heading = f'{subject} {season}赛季薪水对比'
    elif query.get('top'):
        subject = ' · '.join(scope) or 'NBA球员'
        if query.get('scope') == 'active':
            subject += '（现役）'
        direction = '最低' if order == 'asc' else '最高'
        heading = f'{subject} {season}赛季{initial_label}{direction}前{query["top"]}名'
    elif len(records) == 1:
        heading = f'{player_labels[0]} {season}赛季税后薪水'
    else:
        heading = f'{" · ".join(scope) or "NBA球员"} {season}赛季薪水一览'
    subtitle = '税前薪水与税后估算' if query.get('kind') == 'comparison' else f'本次展示{len(records)}名球员 · 合同收入估算'
    from player_context import context
    media_path = ROOT / 'assets/player-media-2026-27.json'
    media = json.loads(media_path.read_text(encoding='utf-8')) if media_path.is_file() else {}
    for part in ('player-media-portraits-2-2026-27.json', 'player-media-portraits-3-2026-27.json'):
        path = ROOT / 'assets' / part
        if path.is_file():
            media.setdefault('players', {}).update(json.loads(path.read_text(encoding='utf-8')).get('players', {}))
    rows, ids = [], set()
    for index, r in enumerate(records):
        identifier = str(r['player_id'])
        if identifier in ids:
            raise ValueError('Duplicate player ID in chart query')
        ids.add(identifier)
        esc = r['escrow_scenario']
        baseline = r['contract_baseline']
        active = bool(r['active_roster'])
        label = r.get('roster_status_label') or ('现役' if active else '非现役·保留付款')
        team = r['team_tax_context']
        row = {
            'id': identifier, 'name': names.get(identifier, r['player']), 'english': r['player'],
            'age': r.get('age'), 'birth': r.get('birth_date'), 'active': active,
            'status': label, 'team': r.get('roster_team_display') or ('' if active else '付款球队：') + team['display_team'],
            'taxFree': bool(team['team_in_no_state_income_tax_state']), 'state': team.get('team_state_zh') or team.get('team_state'),
            'filing': FILING.get(r['filing_scenario']['status'], r['filing_scenario']['status']),
            'filingNote': r['filing_scenario'].get('note', '采用公开资料工资情景，不确认个人真实申报身份。'),
            'net': money(r['estimated_net_usd']), 'netLabel': money(r['rounded_net_usd']),
            'gross': money(r['spotrac_salary_usd']), 'settledGross': money(r['gross_usd']),
            'tax': money(r['estimated_tax_usd']), 'baseline': money(baseline['estimated_net_usd']),
            'baselineLabel': money(baseline['rounded_net_usd']),
            'reduction': money(r['settlement_impact']['gross_reduction_usd']),
            'supplement': money(r.get('extra_settlement_bonus_usd', 0)),
            'cup': money(r.get('extra_cup_bonus_usd', 0)),
            'withheld': money(r['cashflow_scenario']['temporary_escrow_usd']),
            'rate': money(esc['final_reduction_rate']), 'initial': index,
            'source': safe_url(r['sources']['salary']), 'notes': r.get('specific_uncertainties', []),
        }
        row['contract'] = deepcopy(r.get('contract_context') or context(identifier, active))
        row['contract']['source'] = safe_url(row['contract'].get('source'))
        portrait = media.get('players', {}).get(identifier, {})
        logo = media.get('teams', {}).get(r.get('team'), {})
        row['portrait'] = portrait.get('image_data', '') if portrait.get('status') == 'available' else ''
        row['logo'] = logo.get('image_data', '') if logo.get('status') == 'available' else ''
        row['mediaSource'] = safe_url(portrait.get('image_source_page') or portrait.get('player_url'))
        row['mediaProvider'] = portrait.get('media_provider', 'ESPN')
        row['mediaNote'] = portrait.get('image_note', '头像可能为早期照片，球衣不用于判断当前球队。')
        row['portraitStatus'] = portrait.get('status', 'unavailable')
        rows.append(row)
    first = records[0] if records else {}
    esc = first.get('escrow_scenario', {})
    return {
        'schema': 'nba-ledger/1', 'style': STYLE_VERSION, 'heading': heading, 'subtitle': subtitle,
        'season': payload.get('season', '2026-27'), 'salaryDate': payload.get('salary_captured_date', first.get('captured_date', '未知')),
        'ageDate': query.get('age_as_of', first.get('age_as_of', '未知')), 'metric': metric, 'order': order,
        'scope': query.get('scope_note', first.get('roster_status_note', '按薪资快照分类。')),
        'settlement': query.get('settlement_note') or esc.get('label') or '请参阅查询中的结算情景',
        'notice': payload.get('estimate_notice', '公开资料的情景估算，非私人税单或银行到账。'),
        'uncertainties': payload.get('common_uncertainties', []), 'rows': rows,
    }


def table_markdown(data):
    def cell(value):
        return str(value).replace('|', '\\|').replace('\n', ' ')
    lines = [f"# {data['heading']} · {data['subtitle']}", '',
             f"{data['season']}赛季；年龄截至{data['ageDate']}；薪资快照{data['salaryDate']}。单位：万美元。", '',
             '| 序号 | 球员 | 年龄 | 状态 | 球队或付款球队 | 合同税前 | 税后估值 | 零调整基准 | 申报情景 | 当前合同 | 未来续约 |',
             '|---:|---|---:|---|---|---:|---:|---:|---|---|---|']
    for i, row in enumerate(data['rows'], 1):
        values = [i, row['name'], row['age'] if row['age'] is not None else '未知', row['status'], row['team'] + (' · 免税州' if row['taxFree'] and '免税州' not in row['team'] else ''),
                  display(row['gross'], 2), display(row['netLabel']), display(row['baselineLabel']), row['filing'], row['contract']['current_summary'], row['contract']['extension_summary']]
        lines.append('| ' + ' | '.join(cell(x) for x in values) + ' |')
    lines += ['', '## 计算说明', '', '结算口径：' + data['settlement'], '', data['notice'], '', '范围：' + data['scope'], '',
              '排序基于未取整金额；零调整基准仅移除本季扣减与补发，其他假设保持一致。合同总额、保障及均薪是合同资料，不替代本季工资；未来续约单独列示。合同核对日期：2026-10-10；未核实项明确标记。', '']
    lines += ['- ' + x for x in data['uncertainties']]
    lines += ['', '薪资来源：'] + ['- [' + cell(r['name']) + '](' + r['source'] + ')' for r in data['rows'] if r['source']]
    return '\n'.join(lines) + '\n'


def static_table(data):
    e = html.escape
    cells = []
    for i, row in enumerate(data['rows'], 1):
        values = [str(i), row['name'], str(row['age']) if row['age'] is not None else '未知', row['status'], row['team'] + (' · 免税州' if row['taxFree'] and '免税州' not in row['team'] else ''),
                  display(row['gross'], 2), display(row['netLabel']), display(row['baselineLabel']), row['filing'], row['contract']['current_summary'], row['contract']['extension_summary']]
        cells.append('<tr>' + ''.join('<td>' + e(v) + '</td>' for v in values) + '</tr>')
    return ''.join(cells)


def write_chart(payload, destination):
    destination = Path(destination).expanduser().resolve()
    if destination.suffix.lower() != '.html':
        raise ValueError('--chart must end in .html')
    source = deepcopy(payload)
    if 'delivery' not in source:
        from result_quality import metadata
        source['delivery'] = metadata()
    source.pop('visualization', None)
    data = chart_data(source)
    encoded = json.dumps(data, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    for original, escaped in [('&', '\\u0026'), ('<', '\\u003c'), ('>', '\\u003e'), ('\u2028', '\\u2028'), ('\u2029', '\\u2029')]:
        encoded = encoded.replace(original, escaped)
    template = (ROOT / 'assets/chart-template.html').read_text(encoding='utf-8')
    for placeholder, name in [('__CJK_FONT__', 'NotoSansSC-subset.woff2'), ('__NUMBER_FONT__', 'BarlowSemiCondensed-latin.woff2')]:
        template = template.replace(placeholder, base64.b64encode((ROOT / 'assets/fonts' / name).read_bytes()).decode('ascii'))
    licenses = '\n\n'.join((ROOT / 'assets/fonts' / name).read_text(encoding='utf-8') for name in ['NotoSansSC-OFL.txt', 'BarlowSemiCondensed-OFL.txt'])
    template = template.replace('__FONT_LICENSES__', '<pre>' + html.escape(licenses) + '</pre>')
    template = template.replace('__DATA_JSON__', encoded).replace('__STATIC_TABLE__', static_table(data))
    template = template.replace('__PAGE_TITLE__', html.escape(data['heading'] + ' · ' + data['subtitle']))
    difference = source.get('salary_breakdown', {}).get('difference')
    difference_md = ''
    if difference:
        caption = '税后差距拆解（第一位减第二位）'
        rows = ''.join('<tr><td>'+html.escape(x['label'])+'</td><td>'+f"{x['amount']/10000:+,.2f}"+'</td></tr>' for x in difference['steps'] if x['amount'])
        panel = '<section class="table-section"><h2>'+caption+'</h2><p>单位：万美元；正数增加第一位优势，负数减少优势。会计差额分解，不是换队模拟。</p><table class="difference-table"><thead><tr><th>项目</th><th>差距贡献</th></tr></thead><tbody>'+rows+'<tr><th>税后差距</th><td>'+f"{difference['net_difference']/10000:+,.2f}"+'</td></tr></tbody></table></section>'
        template = template.replace('</main>', panel+'</main>')
        difference_md = '\n\n## '+caption+'\n\n| 项目 | 差距贡献（万美元） |\n|---|---:|\n'+'\n'.join(f"| {x['label']} | {x['amount']/10000:+,.2f} |" for x in difference['steps'] if x['amount'])+'\n\n会计差额分解，不是换队因果模拟。\n'
    template = template.replace('</style>', '.difference-table{min-width:0!important;width:100%;table-layout:fixed}.difference-table th,.difference-table td{min-width:0!important;white-space:normal;overflow-wrap:anywhere}.difference-table th:first-child,.difference-table td:first-child{width:65%}.difference-table td:last-child{text-align:right;font-variant-numeric:tabular-nums}</style>', 1)
    if source.get('story_pack'):
        studio = html.escape(Path(source['story_pack']['studio']).name, quote=True)
        entry = '<section class="table-section"><h2>工资去向与视频素材</h2><p>16:9完整分幕素材；下方直接预览。无配音，口播稿单独提供。</p><details><summary>展开完整工资去向图与导出工具</summary><iframe title="工资去向与素材" loading="lazy" src="'+studio+'" style="width:100%;height:760px;border:1px solid #343c3e"></iframe></details><p><a href="'+studio+'">单独打开素材页</a></p></section>'
        video=source['story_pack'].get('video')
        if video and video.get('verification',{}).get('cfr_verified'):
            import os
            video_url=html.escape(os.path.relpath(video['path'],destination.parent),quote=True)
            entry=entry.replace('</section>','<h3>完整视频 · 无配音</h3><video controls preload="metadata" style="width:100%;aspect-ratio:16/9" src="'+video_url+'"></video><p><a download href="'+video_url+'">下载已验证的MP4视频</a></p></section>')
        else:
            entry=entry.replace('</section>','<p>MP4尚未生成；当前提供图片素材与口播稿。</p></section>')
        template = template.replace('<section class="table-section"', entry+'<section class="table-section"', 1)
    info=source['delivery']
    stamp='<p class="chart-caption">Skill '+html.escape(info['skill_version'])+' · 生成 '+html.escape(info['generated_at'])+' · 税则/模型 '+html.escape(str(source.get('model_version','未记录')))+' · 数据快照 '+html.escape(str(source.get('salary_captured_date',source.get('captured_date','未记录'))))+'</p>'
    template=template.replace('</main>',stamp+'</main>')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(template, encoding='utf-8')
    markdown = destination.with_suffix('.md')
    data_file = destination.with_suffix('.json')
    markdown.write_text(table_markdown(data) + difference_md, encoding='utf-8')
    data_file.write_text(json.dumps(source, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    return {'html': str(destination), 'table_markdown': str(markdown), 'data_json': str(data_file),
            'style': STYLE_VERSION, 'scope': 'returned_query_roster_only'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='Successful take_home.py JSON result')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = write_chart(json.loads(args.input.read_text(encoding='utf-8')), args.output)
    except (ValueError, KeyError, OSError) as error:
        parser.exit(2, str(error) + '\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
