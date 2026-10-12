"""Import only the current public DARKO leaderboard, without executing remote JS."""
import argparse, datetime, hashlib, json, math, re, unicodedata, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
URL='https://beta.darko.app/'
def normalize(s):
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower())
def parse(html):
    decoder=json.JSONDecoder()
    pos=html.index('players:{keys:')+len('players:{keys:')
    keys,n=decoder.raw_decode(html[pos:])
    pos=html.index('values:',pos+n)+len('values:')
    # JS allows .5 and -.5. Preserve all quoted strings; normalize numeric tokens only.
    raw=re.sub(r'"(?:\\.|[^"\\])*"|(?<![\w.])(-?)\.(\d+)',lambda m:m[0] if m[0].startswith('"') else m[1]+'0.'+m[2],html[pos:])
    columns,_=decoder.raw_decode(raw)
    if len(keys)!=len(columns) or len({len(c) for c in columns})!=1:raise ValueError('DARKO schema/column lengths changed')
    rows=[dict(zip(keys,values)) for values in zip(*columns)]
    if len(rows)<400 or len({r['nba_id'] for r in rows})!=len(rows):raise ValueError('Incomplete or duplicated leaderboard')
    for r in rows:
        for field in ['sal_market_fixed','dpm']:
            if r[field] is not None and (not isinstance(r[field],(float,int)) or not math.isfinite(r[field])):raise ValueError('Invalid value')
    date=re.search(r'ratingsThrough:"(\d{4}-\d{2}-\d{2})"',html).group(1)
    return rows,date

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--html',type=Path);p.add_argument('--output',type=Path,default=ROOT/'assets/darko-current.json');a=p.parse_args()
    raw=a.html.read_bytes() if a.html else urllib.request.urlopen(URL,timeout=45).read()
    rows,date=parse(raw.decode())
    names=json.loads((ROOT/'assets/player-name-index-2026-27.json').read_text())['players']
    index={}
    for r in rows:index.setdefault(normalize(r['player_name']),[]).append(r)
    matches={};unmatched=[]
    for r in names:
        aliases={'Herb Jones':'Herbert Jones','Alex Sarr':'Alexandre Sarr','Ron Holland II':'Ronald Holland II','Bub Carrington':'Carlton Carrington','Sviatoslav Mykhailiuk':'Svi Mykhailiuk','Craig Porter Jr.':'Craig Porter','Cameron Christie':'Cam Christie','David Jones-Garcia':'David Jones'}
        found=index.get(normalize(aliases.get(r['english_name'],r['english_name'])),[])
        if len(found)==1:matches[str(r['player_id'])]=found[0]['nba_id']
        else:unmatched.append({'player_id':r['player_id'],'name':r['english_name']})
    result={'source':URL,'methodology_url':URL+'about/fair-salary','captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'ratings_through':date,'source_sha256':hashlib.sha256(raw).hexdigest(),'value_field':'sal_market_fixed','currency':'USD','salary_basis':'DARKO actual_salary is expressed in 2025-26 cap dollars; not our 2026-27 Spotrac cash salary','players':rows,'spotrac_to_nba':matches,'unmatched_salary_players':unmatched}
    temp=a.output.with_suffix('.tmp');temp.write_text(json.dumps(result,ensure_ascii=False,indent=2));temp.replace(a.output)
    print(json.dumps({'players':len(rows),'matched':len(matches),'unmatched':unmatched,'ratings_through':date},ensure_ascii=False))
if __name__=='__main__':main()
