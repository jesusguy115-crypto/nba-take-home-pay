#!/usr/bin/env python3
"""Fast offline entry point. Python 3 standard library only."""
import argparse
import json
from pathlib import Path
import sys

from player_names import resolve, mentioned_team, requires_clarification
from duty_days import TEAMS, make_ledger
from state_labels import add_state_label

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'assets/net-estimates-2026-27.json'

def read(path):return json.loads(path.read_text(encoding='utf-8'))

def main():
    parser=argparse.ArgumentParser(description='2026–27 NBA 税后合同收入：离线情景估算')
    parser.add_argument('player',nargs='?',help='中文别名、英文姓名或 Spotrac ID')
    parser.add_argument('--json',action='store_true',help='返回缓存金额、逐税项、假设和来源')
    parser.add_argument('--explain',action='store_true',help='返回完整逐档税额、分摊及抵免 JSON')
    parser.add_argument('--ledger',action='store_true',help='返回逐日假设地点和依据 JSON')
    parser.add_argument('--scenario',type=Path,help='可选个人情景 JSON 文件')
    parser.add_argument('--filing-status',choices=['single','mfj','individual_canada'],help='指定比较情景；不声明球员真实报税身份')
    parser.add_argument('--coverage',action='store_true',help='查看缓存覆盖情况')
    args=parser.parse_args()
    if not CACHE.exists():
        required=['salaries-2026-27.json','salaries-2025-26.json',
                  'schedule-2026-27.json','player-tax-profiles-2026-27.json']
        missing=[name for name in required if not (ROOT/'assets'/name).is_file()]
        if missing:
            parser.exit(2,'尚未导入数据，不能提供球员税后数字。缺少：'+', '.join(missing)+
                        '。请按发行包 DATA_FORMAT.md 使用 import_data.py 导入有权使用的数据；'
                        'build_estimates.py 只计算已有数据，不会获取薪资或赛程。\n')
        parser.exit(2,'税后缓存缺失；输入已齐备，请使用 Python 3 的 -X utf8 模式运行同目录 build_estimates.py。不要编造结果。\n')
    cache=read(CACHE)
    if args.coverage:
        print(json.dumps({k:v for k,v in cache.items() if k!='estimates'},ensure_ascii=False,indent=2));return
    if not args.player:parser.error('请输入球员姓名，或使用 --coverage')
    matches=resolve(cache['estimates'],args.player)
    if len(matches)!=1 or requires_clarification(cache['estimates'],args.player,matches):
        data={'status':'ambiguous' if matches else 'not_found','query':args.player,
              'candidates':[{'player':p['player'],'team':p['team'],'player_id':p['player_id']} for p in matches]}
        if args.json or args.explain:print(json.dumps(data,ensure_ascii=False,indent=2))
        else:
            print('姓名有歧义，请用下列英文全名查询：' if matches else '缓存未匹配到此姓名，请提供英文全名；不以相似姓名代替。')
            for p in matches:print(f"- {p['player']}（{p['team_zh']}，ID {p['player_id']}）")
        return 2
    result=matches[0]
    # Hash salary/schedule/model sources: do not silently serve stale estimates.
    from estimate import model_fingerprint, estimate_player, load
    if model_fingerprint()!=cache['model_fingerprint']:
        parser.exit(2,'输入数据或税则已改变，请运行 build_estimates.py 重建缓存后再查询。\n')
    if args.scenario or args.explain or args.ledger or args.filing_status:
        salaries=load('salaries-2026-27.json')
        player=next(p for p in salaries['players'] if p['player_id']==result['player_id'])
        scenario=read(args.scenario) if args.scenario else {}
        if args.filing_status:scenario['filing_status']=args.filing_status
        try:
            result=estimate_player(player,salaries,load('salaries-2025-26.json'),load('schedule-2026-27.json'),scenario,full=True)
            if not args.scenario:result['filing_scenarios']=matches[0]['filing_scenarios']
        except (ValueError,TypeError,KeyError) as e:parser.exit(2,'无法计算该情景：'+str(e)+'\n')
        if args.ledger:
            print(json.dumps(make_ledger(result['team'],load('schedule-2026-27.json')['games'],(scenario or {}).get('duty_day_overrides')),ensure_ascii=False,indent=2));return
    mentioned=mentioned_team(args.player)
    add_state_label(result)
    if mentioned and mentioned!=result['team']:
        result['team_correction']=f"你提到{TEAMS[mentioned][0]}；{result['player']} 在本快照中对应{result['team_zh']}。"
    if args.json or args.explain:
        # Keep fast answers small; complete calculation records remain --explain.
        output=result if args.explain else {k:v for k,v in result.items() if k not in {'years','source_distribution','duty_summary','assumptions'}}
        print(json.dumps(output,ensure_ascii=False,indent=2));return
    labels={'single':'Single工资情景','mfj':'夫妻合报工资情景','individual_canada':'加拿大个人申报情景'}
    chosen=result['filing_scenario']['status']
    print(f"{result['player']}（{result['team_tax_context']['display_team']}）2026–27 赛季税后合同收入估计约 {result['rounded_net_usd']/10000:,.0f} 万美元（{labels[chosen]}）。")
    print(f"这是公开资料情景估算，非真实税单或银行到账。Spotrac 税前现金薪资 ${result['spotrac_salary_usd']:,.0f}；估计税负 {result['effective_tax_rate']:.1%}。数据截至 {result['captured_date']}。")
    if result.get('team_correction'):print(result['team_correction'])
    if result['team_tax_context']['team_in_no_state_income_tax_state']:
        print('免税州说明：'+result['team_tax_context']['scope_note'])
    if len(result.get('filing_scenarios',{}))>1:
        single=result['filing_scenarios']['single']['rounded_net_usd']/10000
        joint=result['filing_scenarios']['mfj']['rounded_net_usd']/10000
        print(f'身份对照：Single约{single:,.0f}万美元；夫妻合报、仅纳入球员工资约{joint:,.0f}万美元。不是实际误差区间。')
    print('主要不确定因素：')
    for line in [
        '居民地与申报身份：假设球队城市居民；申报情景见上，实际申报方式、配偶收入与个人扣除未知。',
        '客场工作日：比赛地点已缓存；训练、旅行和休息日位置为代理，仍有每队2场未定。',
        '伤病与下放：默认随队；未随队康复或 G 联赛服务会改变收入归属及税额。',
        '税年与税则：采用24期发薪假设；2027未发布参数沿用2026，已立法变化另计。',
        '额外奖金与行程：不默认加入杯赛奖金、季后赛奖金、季后赛或异地季前赛工作日。',
        '税务与到账差异：个人抵免、协定资格、汇率、联盟托管和经纪费可能改变结果。',
    ]+result['specific_uncertainties']:
        print('- '+line)
    if result.get('cashflow_scenario'):
        c=result['cashflow_scenario'];print(f"另按指定费用及临时托管扣除后的现金流情景：${c['net_after_assumed_fees_and_escrow_usd']:,.0f}；托管并非最终税负。")
    print('薪资来源：'+result['sources']['salary'])
    print('逐项计算：同一命令加 --explain；逐日假设账：加 --ledger。')

if __name__=='__main__':sys.exit(main() or 0)
