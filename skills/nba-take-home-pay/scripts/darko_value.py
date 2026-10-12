"""Attach a dated external valuation; never use it as taxable salary."""
from functools import lru_cache
import json
from pathlib import Path
@lru_cache(maxsize=1)
def snapshot():
    path=Path(__file__).resolve().parents[1]/'assets/darko-current.json'
    if not path.exists():return {},{}
    data=json.loads(path.read_text())
    return data,{str(r['nba_id']):r for r in data['players']}
def value_for(player_id):
    data,rows=snapshot()
    row=rows.get(str(data.get('spotrac_to_nba',{}).get(str(player_id))))
    result={'status':'available' if row and row.get('sal_market_fixed') is not None else 'unavailable','value_usd':row.get('sal_market_fixed') if row else None,'ratings_through':data.get('ratings_through'),'captured_at':data.get('captured_at'),'source':data.get('source','https://beta.darko.app/'),'label':'DARKO价值估算','note':'年化球场价值模型估算，非实际收入或合同报价；与2026–27薪资日期/工资帽口径不同，不自动计算超值差额。'}
    if row:result.update(nba_id=row['nba_id'],dpm=row['dpm'],source_season=row['season'],source_team=row['team_name'])
    return result
