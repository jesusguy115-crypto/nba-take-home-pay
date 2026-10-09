#!/usr/bin/env python3
"""Deterministic, explicitly hypothetical player itinerary, never an attendance log."""
from collections import Counter
from datetime import date, timedelta

TEAMS = {
    'ATL': ('老鹰','GA','Atlanta'), 'BOS': ('凯尔特人','MA','Boston'),
    'BKN': ('篮网','NY','Brooklyn'), 'CHA': ('黄蜂','NC','Charlotte'),
    'CHI': ('公牛','IL','Chicago'), 'CLE': ('骑士','OH','Cleveland'),
    'DAL': ('独行侠','TX','Dallas'), 'DEN': ('掘金','CO','Denver'),
    'DET': ('活塞','MI','Detroit'), 'GSW': ('勇士','CA','San Francisco'),
    'HOU': ('火箭','TX','Houston'), 'IND': ('步行者','IN','Indianapolis'),
    'LAC': ('快船','CA','Inglewood'), 'LAL': ('湖人','CA','Los Angeles'),
    'MEM': ('灰熊','TN','Memphis'), 'MIA': ('热火','FL','Miami'),
    'MIL': ('雄鹿','WI','Milwaukee'), 'MIN': ('森林狼','MN','Minneapolis'),
    'NOP': ('鹈鹕','LA','New Orleans'), 'NYK': ('尼克斯','NY','New York'),
    'OKC': ('雷霆','OK','Oklahoma City'), 'ORL': ('魔术','FL','Orlando'),
    'PHI': ('76人','PA','Philadelphia'), 'PHX': ('太阳','AZ','Phoenix'),
    'POR': ('开拓者','OR','Portland'), 'SAC': ('国王','CA','Sacramento'),
    'SAS': ('马刺','TX','San Antonio'), 'TOR': ('猛龙','ON','Toronto'),
    'UTA': ('爵士','UT','Salt Lake City'), 'WAS': ('奇才','DC','Washington'),
}

def home_location(team):
    _, state, city = TEAMS[team]
    return {'country': 'CA' if team == 'TOR' else 'US', 'state': state, 'city': city}

def venue(game):
    return {'country': game['arena_country'], 'state': game['arena_state'], 'city': game['arena_city']}

def location_key(loc):
    return '|'.join(str(loc.get(k) or '') for k in ('country','state','city'))

def make_ledger(team, games, overrides=None):
    """One row per calendar date. Fractional weights are modeling choices, not state law.

    Known games fix venues, not player attendance. Preseason/camp days default home.
    Away gaps <=4 days stay on road; one relocation day receives half a practice day.
    Longer gaps return home. Unassigned Cup dates retain the ordinary gap assumption.
    """
    home = home_location(team)
    selected = sorted((g for g in games if team in (g['home'],g['away'])), key=lambda g:g['date_et'])
    by_date = {g['date_et']:g for g in selected}
    if len(by_date) != len(selected):
        raise ValueError('Duplicate game date for '+team)
    start, end = date(2026,9,29), date(2027,4,11)
    gd = [(date.fromisoformat(g['date_et']),g) for g in selected]
    rows=[]
    for n in range((end-start).days+1):
        day=start+timedelta(days=n); ds=day.isoformat()
        if ds in by_date:
            g=by_date[ds]
            rows.append({'date':ds, **venue(g), 'activity':'scheduled_game', 'weight':1.0,
                         'basis':'published_venue_assumed_attendance', 'game_id':g['game_id']})
            continue
        prev=next(((d,g) for d,g in reversed(gd) if d<day),None)
        nxt=next(((d,g) for d,g in gd if d>day),None)
        loc=home; weight=1.0; activity='assumed_home_duties'
        if prev and nxt:
            pd,pg=prev; nd,ng=nxt
            pl,nl=venue(pg),venue(ng)
            pa,na=location_key(pl)!=location_key(home),location_key(nl)!=location_key(home)
            if pa and na and (nd-pd).days<=4:
                loc=nl
                if location_key(pl)!=location_key(nl) and day==pd+timedelta(days=1):
                    activity='assumed_travel_and_practice'; weight=0.5
                else: activity='assumed_road_duties'
            elif pa and day==pd+timedelta(days=1):
                activity='assumed_travel_and_practice'; weight=0.5
            elif na and day==nd-timedelta(days=1):
                loc=nl; activity='assumed_travel_and_practice'; weight=0.5
        elif nxt and day==nxt[0]-timedelta(days=1) and location_key(venue(nxt[1]))!=location_key(home):
            loc=venue(nxt[1]);activity='assumed_travel_and_practice';weight=0.5
        if day<date(2026,10,20) and activity=='assumed_home_duties':
            activity='assumed_camp_home_duties'
        rows.append({'date':ds,**loc,'activity':activity,'weight':weight,'basis':'modeled_not_observed'})
    for override in overrides or []:
        a=date.fromisoformat(override['start']);b=date.fromisoformat(override.get('end',override['start']))
        if a>b:raise ValueError('Override start is after end')
        activity=override['activity']
        allowed={'game','practice','rehab_team','rehab_private','injured_no_duties','travel_only','g_league_game','g_league_practice','postseason_duties'}
        if activity not in allowed: raise ValueError('Unsupported activity: '+activity)
        if any(k not in override for k in ('country','state','city')):raise ValueError('Override requires country,state,city')
        for i in range((b-a).days+1):
            ds=(a+timedelta(days=i)).isoformat()
            row={'date':ds,**{k:override[k] for k in ('country','state','city')},'activity':activity,
                 'weight':0.0 if activity in {'injured_no_duties','rehab_private','travel_only'} else 1.0,
                 'basis':'user_supplied_override','evidence':override.get('evidence','user supplied, unverified')}
            matches=[j for j,x in enumerate(rows) if x['date']==ds]
            if matches: rows[matches[0]]=row
            else: rows.append(row)
    return sorted(rows,key=lambda r:r['date'])

def summarize(rows):
    weights=Counter(); counts=Counter(); activities=Counter()
    for row in rows:
        k=location_key(row);weights[k]+=row['weight'];counts[k]+=1;activities[row['activity']]+=1
    total=len(rows)
    return {
        'calendar_days':total, 'weighted_source_days':round(sum(weights.values()),6),
        'unallocated_travel_or_injury_days':round(total-sum(weights.values()),6),
        'locations':[{'country':k.split('|')[0],'state':k.split('|')[1],'city':k.split('|')[2],
                      'calendar_days':counts[k],'weighted_days':round(v,6),'income_share':v/total}
                     for k,v in sorted(weights.items())],
        'activities':dict(activities),
        'method':'calendar_itinerary_proxy_v1; not statutory duty-day certification',
    }
