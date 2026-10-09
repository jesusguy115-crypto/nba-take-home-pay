#!/usr/bin/env python3
"""Fast offline queries; calculations run only for explicit detail/scenario requests."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

from player_names import resolve, mentioned_team, requires_clarification, name_index_coverage, TEAM_NAMES
from duty_days import TEAMS, make_ledger
from state_labels import add_state_label

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'assets/net-estimates-2026-27.json'
LABELS = {'single': 'Single工资情景', 'mfj': '夫妻合报工资情景',
          'individual_canada': '加拿大个人申报情景'}
AMOUNT_FIELDS = ('estimated_net_usd', 'rounded_net_usd', 'estimated_tax_usd',
                 'effective_tax_rate', 'components_usd')
SCENARIO_FIELDS = (*AMOUNT_FIELDS, 'filing_scenario', 'specific_uncertainties',
                   'assumptions', 'gross_usd', 'contract_gross_usd',
                   'escrow_scenario', 'contract_baseline', 'settlement_impact',
                   'cashflow_scenario', 'previous_season_adjusted_gross_usd',
                   'calculation_type', 'extra_settlement_bonus_usd')
FULL_ONLY = {'years', 'source_distribution', 'duty_summary', 'assumptions'}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def positive_int(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError('人数必须大于零')
    return number


def team_code(value):
    code = value.upper()
    if code in TEAMS:
        return code
    if value in TEAM_NAMES:
        return TEAM_NAMES[value]
    raise argparse.ArgumentTypeError('球队未匹配，请用球队代码（如 MIN）或中文队名（如森林狼）')


def cached_scenario(row, status=None, settlement=None):
    """Select precomputed values and their own metadata without invoking the model."""
    result = deepcopy(row)
    if status:
        variant = row.get('filing_scenarios', {}).get(status)
        if variant is None:
            raise ValueError(f"{row['player']} 不支持 {status}；猛龙只使用加拿大个人申报情景，美国球队只支持 Single/MFJ。")
        if status != row['filing_scenario']['status'] and not all(
                field in variant for field in ('filing_scenario', 'specific_uncertainties')):
            raise ValueError('申报情景缓存缺少对应说明，请运行 build_estimates.py 重建；不能把另一情景的说明套到这个金额上。')
        for field in SCENARIO_FIELDS:
            if field in variant:
                result[field] = deepcopy(variant[field])
        # These detailed ledgers describe the default status. Detail requests
        # always recompute, so do not retain them after switching a cached status.
        if status != row['filing_scenario']['status']:
            for field in ('years', 'source_distribution', 'duty_summary', 'assumptions'):
                result.pop(field, None)
    if not all(field in result for field in ('escrow_scenario', 'contract_baseline', 'settlement_impact', 'cashflow_scenario')):
        raise ValueError('缓存缺少联盟结算层，请运行 build_estimates.py 重建；不能把旧税后数字当成结算后收入。')
    if settlement == 'baseline':
        baseline = result['contract_baseline']
        if not all(field in baseline for field in (*AMOUNT_FIELDS, 'escrow_scenario', 'cashflow_scenario')):
            raise ValueError('缓存缺少完整合同基准，请运行 build_estimates.py 重建。')
        for field in SCENARIO_FIELDS:
            if field in baseline and field != 'contract_baseline':
                result[field] = deepcopy(baseline[field])
        result['filing_scenarios'] = {
            name: deepcopy(variant['contract_baseline'])
            for name, variant in row.get('filing_scenarios', {}).items()
        }
        for field in FULL_ONLY:
            result.pop(field, None)
    if status and status != 'individual_canada':
        result['filing_scenario']['selection_reason'] = 'user_requested_counterfactual'
    result['query_path'] = 'precomputed_cache'
    return add_state_label(result)


def schedule_note(cache, team=None):
    coverage = cache.get('schedule_coverage', {})
    missing_by_team = coverage.get('unassigned_games_per_team', {})
    if team in missing_by_team:
        missing = missing_by_team[team]
        detail = f'该队尚有{missing}场常规赛未定' if missing else '该队常规赛对阵已全部缓存'
    elif 'unassigned_regular_games' in cache:
        detail = f"全联盟尚有{cache['unassigned_regular_games']}场常规赛未定"
    else:
        detail = '未定比赛数量以赛程覆盖记录为准'
    return f'客场工作日：{detail}；比赛不等于实际出席，训练、旅行和休息日地点仍为代理。'


def common_uncertainties(cache, team=None, residence=None, settlement=None):
    location = '球队城市' if residence is None else ' '.join(str(residence.get(k) or '') for k in ('country', 'state', 'city')).strip()
    rate = (settlement or {}).get('final_reduction_rate', 0.0548)
    withholding = (settlement or {}).get('withholding_rate', 0.10)
    supplemental = (settlement or {}).get('settlement_bonus_usd', 0)
    settlement_caveat = (f'联盟结算：2026–27最终扣减率尚未确定；本结果采用{rate:.2%}扣减情景，税款已按该工资情景计算。'
                         if rate or supplemental else '联盟结算：本结果是本季扣减及补发均为零的税后基准，不代表已知全额返还；2026–27最终扣减率尚未确定。')
    return [
        f'居民地与申报：采用{location}居民情景；真实税籍、申报方式、配偶收入和个人扣除未知。',
        schedule_note(cache, team),
        '伤病与下放：默认随队；异地康复或G联赛服务会改变税源分摊。',
        '跨税年：按24期发薪分配；2027未发布税则参数沿用2026代理，已立法变化另计。',
        '额外收入和行程：默认不加杯赛/季后赛奖金、季后赛和异地季前赛工作日。',
        settlement_caveat,
        f'现金时点：{withholding:.2%}发薪暂扣与最终工资扣减不可重复相减；本结果不预测工资预扣或返还日期。',
        '实际到账：协定、汇率、抵免、经纪费、NBPA会费和个人扣款仍会影响结果。',
    ]


def filing_note(result):
    status = result['filing_scenario']['status']
    married = result['tax_profile']['marital_status'] in ('married', 'married_reported')
    if status == 'individual_canada':
        return '加拿大个人申报；税籍、公民身份及协定资格为模型假设。'
    if status == 'single' and married:
        return '公开记录已婚，Single仅为指定反事实比较，不表示依法可按Single申报。'
    if status == 'mfj' and result['filing_scenario'].get('spouse_income_status') == 'user_supplied_wages':
        return 'MFJ使用指定配偶工资，共同所得税按工资比例归属球员；真实报税和税负分配仍未知。'
    if status == 'mfj':
        return 'MFJ仅纳入球员工资，未核实实际合报方式及配偶收入。'
    return '婚姻资料未知，采用Single税表情景；不认定球员单身。'


def brief_result(result):
    """Retain answer-critical evidence; leave tax ledgers and biographies to --json."""
    fields = ('season', 'player_id', 'player', 'team', 'team_zh', 'active_roster',
              'spotrac_salary_usd', 'estimated_net_usd', 'rounded_net_usd',
              'estimated_tax_usd', 'effective_tax_rate', 'team_tax_context',
              'captured_date', 'model_version', 'tax_checked_date', 'query_path',
              'residence_scenario', 'gross_usd', 'contract_gross_usd', 'extra_cup_bonus_usd',
              'escrow_scenario', 'settlement_impact', 'extra_settlement_bonus_usd', 'calculation_type')
    output = {field: result[field] for field in fields}
    output['escrow_scenario'] = {field: result['escrow_scenario'][field] for field in (
        'withholding_rate', 'final_reduction_rate', 'prior_season_final_reduction_rate',
        'settlement_bonus_usd', 'label', 'selection_reason', 'supplemental_payment_status',
        'current_season_rate_status', 'actual_2026_27_rate_known', 'historical_reference_season',
        'prior_season_rate_status', 'legacy_escrow_rate_used')}
    output['escrow_scenario']['timing_note'] = '按24期比例归属税年；实际预扣、返还日期及税务处理未知。'
    output['filing_scenario'] = {
        'status': result['filing_scenario']['status'],
        'selection_reason': result['filing_scenario']['selection_reason'],
        'actual_filing_status': result['filing_scenario']['actual_filing_status'],
        'note': filing_note(result),
    }
    output['tax_profile'] = {key: result['tax_profile'].get(key)
                             for key in ('marital_status', 'actual_filing_status', 'as_of')}
    if result['filing_scenario'].get('spouse_income_status') == 'user_supplied_wages':
        output['filing_scenario']['spouse_wages_by_year'] = result['filing_scenario']['spouse_wages_by_year']
    output['filing_scenarios'] = {
        key: {field: value[field] for field in ('estimated_net_usd', 'rounded_net_usd')}
        for key, value in result.get('filing_scenarios', {}).items()
    }
    output['specific_uncertainties'] = result['specific_uncertainties']
    output['contract_baseline'] = {field: result['contract_baseline'][field]
        for field in ('estimated_net_usd', 'rounded_net_usd', 'estimated_tax_usd', 'gross_usd')}
    output['sources'] = {'salary': result['sources']['salary']}
    for field in ('rank', 'position', 'team_correction', 'cashflow_scenario'):
        if field in result:
            output[field] = result[field]
    if 'cashflow_scenario' in output:
        # Money and unknown actual-payroll fields remain local to each player;
        # the common explanation and source documents appear once per response.
        output['cashflow_scenario'] = {key: value for key, value in output['cashflow_scenario'].items()
                                       if key != 'note'}
    return output


def shared_metadata(cache, team=None, compact=False, residence=None, settlement=None):
    output = {
        'season': cache['season'], 'model_version': cache['model_version'],
        'salary_captured_date': cache['salary_captured_date'],
        'estimate_notice': '公开资料的情景点估计，非真实税单或银行到账；无经真实税单验证的固定误差率。',
        'contract_baseline_note': '本季扣减及补发均为零、保留同一上季扣减假设的税后基准。',
        'common_uncertainties': common_uncertainties(cache, team, residence, settlement),
    }
    for key in ('data_versions', 'schedule_coverage'):
        if key in cache:
            output[key] = cache[key]
    if compact:
        if settlement:
            output['settlement_rules'] = {key: settlement[key] for key in (
                'historical_reference_status', 'tax_timing_policy', 'supplemental_allocation_policy',
                'withholding_scope', 'sources') if key in settlement}
            output['settlement_rules']['cashflow_note'] = '暂扣、返还和补扣均为税前分解，最终扣减只计算一次；未估算实际工资预扣或银行到账。返还时点及税务处理未知。'
        if 'data_versions' in output:
            output['data_versions'] = {category: {key: version[key] for key in ('version', 'as_of') if key in version}
                                       for category, version in output['data_versions'].items()}
        if 'schedule_coverage' in output:
            coverage = output['schedule_coverage']
            output['schedule_coverage'] = {key: coverage[key] for key in
                ('known_regular_season_games', 'expected_regular_season_games', 'unassigned_regular_games') if key in coverage}
            if team:
                output['schedule_coverage']['team'] = team
                output['schedule_coverage']['team_unassigned_games'] = coverage.get('unassigned_games_per_team', {}).get(team)
    return output


def match_error(players, query):
    matches = resolve(players, query)
    if len(matches) == 1 and not requires_clarification(players, query, matches):
        return matches[0], None
    return None, {
        'status': 'ambiguous' if matches else 'not_found', 'query': query,
        'candidates': [{'player': p['player'], 'team': p['team'], 'player_id': p['player_id']}
                       for p in matches],
    }


def sorted_results(rows, basis):
    if not basis:
        return rows
    field = 'spotrac_salary_usd' if basis == 'gross' else 'estimated_net_usd'
    ordered = sorted(rows, key=lambda row: (-row[field], row['player'].casefold(), str(row['player_id'])))
    previous = None
    rank = 0
    for index, row in enumerate(ordered, 1):
        if row[field] != previous:
            rank = index
        row['rank'] = rank
        row['position'] = index
        previous = row[field]
    return ordered


def settlement_label(result):
    settlement = result['escrow_scenario']
    if settlement['final_reduction_rate'] == 0 and not settlement.get('settlement_bonus_usd'):
        return '本季扣减及补发均为零的税后基准'
    if 'historical' in settlement['selection_reason']:
        label = f"按{settlement['final_reduction_rate']:.2%}历史扣减比例参照（非本赛季已知结算）"
    else:
        label = settlement.get('label') or f"本赛季最终扣减率假设{settlement['final_reduction_rate']:.2%}，实际比例未知"
    if settlement.get('settlement_bonus_usd'):
        label += f"，另含指定税前补发${settlement['settlement_bonus_usd']:,.0f}假设"
    return label


def print_single(result, cache, brief=False):
    chosen = result['filing_scenario']['status']
    print(f"{result['player']}（{result['team_tax_context']['display_team']}）2026–27 赛季税后合同收入估计约 {result['rounded_net_usd']/10000:,.0f} 万美元（{settlement_label(result)}；{LABELS[chosen]}）。")
    print(f"本季扣减及补发均为零的税后基准：约{result['contract_baseline']['rounded_net_usd']/10000:,.0f}万美元；保留同一上季扣减假设，2026–27实际结算尚未知。")
    print(f"公开资料情景估算，非真实税单或银行到账。Spotrac税前薪资 ${result['spotrac_salary_usd']:,.0f}；估计税负 {result['effective_tax_rate']:.1%}；数据截至 {result['captured_date']}。")
    print(filing_note(result))
    if result.get('team_correction'):
        print(result['team_correction'])
    if result['team_tax_context']['team_in_no_state_income_tax_state']:
        print('免税州说明：' + result['team_tax_context']['scope_note'])
    variants = result.get('filing_scenarios', {})
    if 'single' in variants and 'mfj' in variants:
        single = variants['single']['rounded_net_usd'] / 10000
        joint = variants['mfj']['rounded_net_usd'] / 10000
        print(f'身份对照：Single约{single:,.0f}万美元；MFJ约{joint:,.0f}万美元。此为身份情景比较，非误差区间。')
    print('主要不确定因素：')
    for line in common_uncertainties(cache, result['team'], result['residence_scenario'], result['escrow_scenario']) + result['specific_uncertainties']:
        print('- ' + line)
    if result.get('cashflow_scenario'):
        cash = result['cashflow_scenario']
        print(f"税前资金分解：发薪暂扣${cash['temporary_escrow_usd']:,.0f}；本情景最终扣减${cash['modeled_final_reduction_usd']:,.0f}；预计可释放${cash['modeled_refund_before_tax_usd']:,.0f}。均为税前情景金额，不是银行到账；不预测释放日期。")
        if cash.get('modeled_additional_collection_before_tax_usd'):
            print(f"假设最终扣减超过暂扣部分，另列待结算${cash['modeled_additional_collection_before_tax_usd']:,.0f}；具体执行机制需核定。")
        if cash.get('supplemental_settlement_payment_before_tax_usd'):
            print(f"另有指定补发工资假设${cash['supplemental_settlement_payment_before_tax_usd']:,.0f}（税前），已纳入应税收入重算；不代表已确定补发。")
        if 'net_after_assumed_agent_fee_usd' in cash:
            print(f"另减指定经纪费后的情景金额：${cash['net_after_assumed_agent_fee_usd']:,.0f}；未再次扣除发薪暂扣。")
    print('薪资来源：' + result['sources']['salary'])
    if not brief:
        print('逐项计算：同一命令加 --explain；逐日假设账：加 --ledger。')


def print_batch(output):
    query = output['query']
    basis = {'gross': '税前合同现金薪资', 'net': '估计税后合同收入', 'input': '输入顺序'}[query['sort']]
    print(f"2026–27赛季，共{output['returned_count']}人；排序依据：{basis}。")
    print('联盟结算情景：' + query['settlement_note'] + '；2026–27实际结算尚未知。')
    print('| 序号 | 球员 | 球队/州 | 合同税前（万美元） | 本情景税后约（万美元） | 未调整基准税后约（万美元） | 申报情景 |')
    print('|---:|---|---|---:|---:|---:|---|')
    for index, row in enumerate(output['results'], 1):
        rank = row.get('rank', index)
        print(f"| {rank} | {row['player']} | {row['team_tax_context']['display_team']} | {row['spotrac_salary_usd']/10000:,.2f} | {row['rounded_net_usd']/10000:,.0f} | {row['contract_baseline']['rounded_net_usd']/10000:,.0f} | {LABELS[row['filing_scenario']['status']]} |")
    print(output['estimate_notice'] + f" 数据截至 {output['salary_captured_date']}。")
    print('未调整基准：' + output['contract_baseline_note'])
    print('查询范围：' + query['scope_note'])
    print('同金额并列名次，按英文姓名和ID稳定排序；截取指定人数。')
    print('免税州仅免州个人所得税，联邦、工资及适用的客场税仍计入。')
    for line in output['common_uncertainties']:
        print('- ' + line)
    for row in output['results']:
        variants = row.get('filing_scenarios', {})
        compare = ''
        if 'single' in variants and 'mfj' in variants:
            compare = f" Single约{variants['single']['rounded_net_usd']/10000:,.0f}万 / MFJ约{variants['mfj']['rounded_net_usd']/10000:,.0f}万美元（非误差区间）。"
        print(f"- {row['player']}：{filing_note(row) if 'tax_profile' in row else row['filing_scenario']['note']}{compare}")
        if row.get('team_correction'):
            print('  ' + row['team_correction'])
        for note in row['specific_uncertainties']:
            print('  ' + note)
        print('  薪资来源：' + row['sources']['salary'])


def main(argv=None):
    parser = argparse.ArgumentParser(description='2026–27 NBA 税后合同收入：离线情景估算')
    parser.add_argument('player', nargs='?', help='中文别名、英文姓名或 Spotrac ID')
    parser.add_argument('--json', action='store_true', help='返回结构化结果；与 --brief 合用精简字段')
    parser.add_argument('--brief', action='store_true', help='保留金额、身份情景、风险及来源的快答输出')
    parser.add_argument('--top', type=positive_int, metavar='N', help='按 --sort 返回前N人，默认税前薪资排序')
    parser.add_argument('--sort', choices=['gross', 'net'], help='按未取整税前薪资gross或税后估值net降序')
    parser.add_argument('--team', type=team_code, help='球队代码或中文队名；默认Active Roster')
    parser.add_argument('--scope', choices=['active', 'all'], help='active为现役名单；all含Dead Money/Retained接收者')
    parser.add_argument('--compare', nargs='+', metavar='PLAYER', help='一次比较多名球员，默认保留输入顺序')
    parser.add_argument('--explain', action='store_true', help='返回完整逐档税额、分摊及抵免 JSON')
    parser.add_argument('--ledger', action='store_true', help='返回逐日假设地点和依据 JSON')
    parser.add_argument('--scenario', type=Path, help='个人情景 JSON 文件；触发重算')
    parser.add_argument('--filing-status', choices=['single', 'mfj', 'individual_canada'], help='从缓存选择身份情景；不声明真实报税身份')
    parser.add_argument('--settlement', choices=['baseline', 'historical'], help='baseline为未作联盟结算调整的基准；historical按5.48%历史扣减比例估算（默认），非2026–27已知结果。与--scenario合用时覆盖扣减率，baseline同时将本季补发设为0')
    parser.add_argument('--coverage', action='store_true', help='查看缓存覆盖情况')
    args = parser.parse_args(argv)
    batch = args.top is not None or args.team is not None or args.compare is not None
    if args.coverage and (args.player or batch or args.scenario or args.explain or args.ledger or args.filing_status or args.settlement or args.scope or args.sort):
        parser.error('--coverage 不能与球员查询、排名、身份或计算情景混用')
    if args.explain and args.ledger:
        parser.error('--explain 与 --ledger 请分别查询')
    if args.player and batch:
        parser.error('单人姓名与 --top/--team/--compare 不能同时使用')
    if args.compare and (args.top or args.team):
        parser.error('--compare 与 --top/--team 不能同时使用')
    if batch and (args.scenario or args.explain or args.ledger):
        parser.error('逐项计算、逐日账和个人情景请指定一名球员；批量查询直接读取缓存')
    if args.brief and (args.explain or args.ledger):
        parser.error('--brief 与 --explain/--ledger 不能同时使用')
    if (args.sort or args.scope) and not batch:
        parser.error('--sort/--scope 需要 --top、--team 或 --compare')
    if args.compare and args.scope:
        parser.error('--compare 按明确姓名查询，不接受 --scope 筛选')
    if not CACHE.exists():
        required = ['salaries-2026-27.json', 'salaries-2025-26.json',
                    'schedule-2026-27.json', 'player-tax-profiles-2026-27.json']
        missing = [name for name in required if not (ROOT / 'assets' / name).is_file()]
        if missing:
            parser.exit(2, '尚未导入数据，不能提供球员税后数字。缺少：' + ', '.join(missing) +
                        '。请按发行包 DATA_FORMAT.md 使用 import_data.py 导入有权使用的数据；'
                        'build_estimates.py 只计算已有数据，不会获取薪资或赛程。\n')
        parser.exit(2, '税后缓存缺失；请使用 Python 3 的 -X utf8 模式运行同目录 build_estimates.py。不要编造结果。\n')
    cache = read(CACHE)
    from estimate import model_fingerprint
    if model_fingerprint() != cache['model_fingerprint']:
        parser.exit(2, '输入数据或税则已改变，请运行 build_estimates.py 重建缓存后再查询。\n')
    if args.coverage:
        coverage = {k: v for k, v in cache.items() if k != 'estimates'}
        coverage['name_index'] = name_index_coverage(cache['estimates'])
        print(json.dumps(coverage, ensure_ascii=False, indent=2))
        return
    if not args.player and not batch:
        parser.error('请输入球员姓名，或使用 --top/--team/--compare/--coverage')
    players = cache['estimates']
    queries = args.compare or ([args.player] if args.player else [])
    errors = []
    selected = []
    if queries:
        seen = set()
        for query in queries:
            row, error = match_error(players, query)
            if error:
                errors.append(error)
            elif row['player_id'] not in seen:
                selected.append((row, query))
                seen.add(row['player_id'])
        if errors:
            payload = errors[0] if not batch else {'status': 'query_errors', 'errors': errors}
            if args.json or args.explain:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                for error in errors:
                    print(f"{error['query']}：姓名有歧义或未匹配，请提供英文全名；不以相似姓名替代。")
                    for row in error['candidates']:
                        print(f"- {row['player']}（{row['team']}，ID {row['player_id']}）")
            return 2
    else:
        scope = args.scope or ('active' if args.team else 'all')
        eligible = [row for row in players if scope == 'all' or row['active_roster']]
        if args.team:
            eligible = [row for row in eligible if
                        (row['team'] == args.team if scope == 'active' else args.team in row['paying_teams'])]
        selected = [(row, None) for row in eligible]
    selected_count = len(selected)
    basis = args.sort or (None if args.compare else 'gross')
    # Gross rank does not depend on filing status. Select first so an unused
    # Canadian player cannot block a US-only Top N comparison. Net rank needs
    # every eligible player's chosen estimate and therefore validates all of them.
    if batch and args.top is not None and basis == 'gross':
        selected.sort(key=lambda pair: (-pair[0]['spotrac_salary_usd'], pair[0]['player'].casefold(), str(pair[0]['player_id'])))
        selected = selected[:args.top]
    results = []
    for original, query in selected:
        try:
            result = cached_scenario(original, None if (args.scenario or args.explain or args.ledger) else args.filing_status,
                                     args.settlement)
        except (ValueError, KeyError) as error:
            parser.exit(2, '无法选择缓存情景：' + str(error) +
                        (' 批量统一身份时不能将美国税表用于猛龙；省略 --filing-status 使用各自默认情景，或指定美国球队/球员。' if batch else '') + '\n')
        if query:
            mentioned = mentioned_team(query)
            if mentioned and mentioned != result['team']:
                result['team_correction'] = f"你提到{TEAMS[mentioned][0]}；{result['player']} 在本快照中对应{result['team_zh']}。"
        results.append(result)
    if batch:
        basis = args.sort or (None if args.compare else 'gross')
        results = sorted_results(results, basis)
        count = selected_count
        if args.top is not None:
            results = results[:args.top]
        scope = 'named_players' if args.compare else args.scope or ('active' if args.team else 'all')
        scope_note = ('仅列指定姓名，重复球员合并一次。' if args.compare else
                      '按当前快照的Active Roster球员列示。' if scope == 'active' else
                      '包括Active Roster、Dead Money及Retained现金接收者。')
        if args.team and scope == 'all':
            scope_note += '按该队付款记录筛选；显示每名球员全部付款球队的总薪资，不是该队单独付款额。'
        else:
            scope_note += '薪资为每名球员全部付款球队的CashTotal合计。'
        settlement = results[0]['escrow_scenario'] if results else {'final_reduction_rate': 0 if args.settlement == 'baseline' else 0.0548}
        output = shared_metadata(cache, args.team, compact=args.brief, settlement=settlement)
        output.update(query={'kind': 'comparison' if args.compare else 'team' if args.team else 'ranking',
                             'team': args.team, 'scope': scope, 'scope_note': scope_note,
                             'sort': basis or 'input', 'top': args.top,
                             'settlement': args.settlement or 'historical',
                             'settlement_note': settlement_label(results[0]) if results else ('本季扣减及补发均为零的税后基准' if args.settlement == 'baseline' else '按5.48%历史扣减比例参照'),
                             'ranking_note': '未取整金额降序；同金额并列名次，再按英文姓名与ID排序；最多返回指定人数。'},
                      matched_count=count, returned_count=len(results),
                      results=[brief_result(row) if args.brief else
                               {k: v for k, v in row.items() if k not in FULL_ONLY} for row in results])
        if args.json:
            print(json.dumps(output, ensure_ascii=False, indent=None if args.brief else 2))
        else:
            print_batch(output)
        return
    result = results[0]
    if args.scenario or args.explain or args.ledger:
        from estimate import estimate_player, load
        salaries = load('salaries-2026-27.json')
        player = next(p for p in salaries['players'] if p['player_id'] == result['player_id'])
        scenario = read(args.scenario) if args.scenario else {}
        if args.filing_status:
            scenario['filing_status'] = args.filing_status
        if args.settlement:
            scenario['final_reduction_rate'] = 0 if args.settlement == 'baseline' else 0.0548
            if args.settlement == 'baseline':
                scenario['settlement_bonus_usd'] = 0
        try:
            recalculated = estimate_player(player, salaries, load('salaries-2025-26.json'),
                                           load('schedule-2026-27.json'), scenario, full=True)
            if args.settlement == 'historical':
                recalculated['escrow_scenario']['selection_reason'] = 'user_requested_historical_reference_preset'
            if not args.scenario:
                recalculated['filing_scenarios'] = result['filing_scenarios']
            if result.get('team_correction'):
                recalculated['team_correction'] = result['team_correction']
            result = add_state_label(recalculated)
            result['query_path'] = 'recomputed_detail_or_scenario'
        except (ValueError, TypeError, KeyError) as error:
            parser.exit(2, '无法计算该情景：' + str(error) + '\n')
        if args.ledger:
            print(json.dumps(make_ledger(result['team'], load('schedule-2026-27.json')['games'],
                                         scenario.get('duty_day_overrides')), ensure_ascii=False, indent=2))
            return
    if args.json or args.explain:
        if args.brief:
            output = brief_result(result)
            output.update(shared_metadata(cache, result['team'], compact=True, residence=result['residence_scenario'],
                                          settlement=result['escrow_scenario']))
        else:
            output = result if args.explain else {k: v for k, v in result.items() if k not in FULL_ONLY}
        print(json.dumps(output, ensure_ascii=False, indent=None if args.brief else 2))
    else:
        print_single(result, cache, args.brief)


if __name__ == '__main__':
    sys.exit(main() or 0)
