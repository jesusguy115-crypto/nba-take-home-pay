"""Offline, ID-based player name lookup shared by every query entry point.

Salary records provide canonical English names. The bundled name registry adds
Chinese translations and curated nicknames; arbitrary substrings never identify
a player. Ambiguous surnames require a full name or a unique team match.
"""
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from duty_days import TEAMS

NAME_INDEX = Path(__file__).resolve().parents[1] / 'assets' / 'player-name-index-2026-27.json'

TEAM_NAMES={v[0]:k for k,v in TEAMS.items()}
TEAM_NAMES.update({'费城':'PHI','七六人':'PHI','小牛':'DAL','开拓者队':'POR','雷霆队':'OKC','森林狼队':'MIN'})
TEAM_NAMES.update({'夏洛特黄蜂':'CHA','波士顿凯尔特人':'BOS','明尼苏达森林狼':'MIN','金州勇士':'GSW',
 '洛杉矶湖人':'LAL','洛杉矶快船':'LAC','纽约尼克斯':'NYK','布鲁克林篮网':'BKN','多伦多猛龙':'TOR',
 '费城76人':'PHI','克利夫兰骑士':'CLE','底特律活塞':'DET','印第安纳步行者':'IND','密尔沃基雄鹿':'MIL',
 '芝加哥公牛':'CHI','亚特兰大老鹰':'ATL','迈阿密热火':'MIA','奥兰多魔术':'ORL','华盛顿奇才':'WAS',
 '丹佛掘金':'DEN','俄克拉荷马雷霆':'OKC','波特兰开拓者':'POR','犹他爵士':'UTA','菲尼克斯太阳':'PHX',
 '萨克拉门托国王':'SAC','达拉斯独行侠':'DAL','休斯顿火箭':'HOU','孟菲斯灰熊':'MEM','新奥尔良鹈鹕':'NOP','圣安东尼奥马刺':'SAS'})
AMBIGUOUS={'鲍尔':['Ball'],'格林':['Green'],'穆雷':['Murray'],'默里':['Murray'],
           '威廉姆斯':['Williams'],'琼斯':['Jones'],'布里奇斯':['Bridges'],
           '汤普森':['Thompson'],'西蒙斯':['Simmons','Simons'],
           '怀特':['White'],'巴恩斯':['Barnes'],'波特':['Porter'],'小波特':['Porter'],
           '霍勒迪':['Holiday'],'阿伦':['Allen'],'艾伦':['Allen'],'里德':['Reid','Reed'],
           '米切尔':['Mitchell'],'鲍威尔':['Powell'],'夏普':['Sharpe'],'乔治':['George']}

# Remove query wording only at the edges, and stop at any recognized name.
# This avoids damaging names that themselves contain a team/city/query token.
QUERY_WORDS = (
    '20262027', '202627', '2026', '2027', '2627', 'nba',
    '下个赛季', '下一赛季', '下赛季', '这个赛季', '本赛季', '新赛季', '本季', '下季', '赛季',
    '我现在想知道', '我现在想查询', '我现在想查', '我现在要', '我现在',
    '请帮我查一下', '帮忙查一下', '帮我查一下', '请帮我', '我想了解', '我想查询',
    '我想知道', '我想查', '帮我查', '查一下', '看一下', '查询', '请问', '请',
    '帮我', '告诉我', '计算', '估算', '查下', '想看', '看看', '给我', '查',
    '实际到手', '税后到手', '税后薪资', '税前薪资', '净收入', '税后', '税前',
    '实际', '到手', '年薪', '薪水', '薪资', '工资', '收入',
    '大概', '大约', '多少钱', '是多少', '多少', '能拿到', '可以拿到', '能拿', '拿到',
    '球员', '现在', '的', '呢', '吗', '啊', '吧',
    'whatis', 'whats', 'howmuchdoes', 'howmuch', 'please',
    'takehomepay', 'takehomesalary', 'netincome', 'netsalary', 'netpay',
    'aftertaxincome', 'aftertaxsalary', 'aftertax', 'beforetax',
    'nextseason', 'thisseason', 'season', 'salary', 'income', 'earn', 'make', 'for', 'in',
)
_SUFFIXES = {'jr', 'sr', 'ii', 'iii', 'iv', 'v'}


def clean(value):
    """Ignore accents, width, case, whitespace and punctuation (including ・)."""
    return ''.join(char for char in unicodedata.normalize('NFKD', str(value)).casefold()
                   if char.isalnum())


@lru_cache(maxsize=4)
def _read_registry(path, modified_ns, size):
    # mtime/size are part of the cache key so an imported index is picked up in
    # a long-lived Python process without caching old aliases indefinitely.
    return json.loads(Path(path).read_text(encoding='utf-8'))


def name_registry():
    """Return the shared registry; bare import fixtures still match English."""
    try:
        stat = NAME_INDEX.stat()
    except FileNotFoundError:
        return {'schema_version': 1, 'season': '2026-27', 'players': []}
    return _read_registry(str(NAME_INDEX), stat.st_mtime_ns, stat.st_size)


def _names_for_record(record):
    names = [record.get('english_name'), record.get('chinese_name')]
    names.extend(record.get('aliases', []))
    return [name for name in names if isinstance(name, str) and name.strip()]


def name_index_coverage(players):
    """Summarize registry coverage against the actual salary/query snapshot."""
    registry = name_registry()
    rows = {str(row['player_id']): row for row in registry.get('players', [])}
    ids = {str(player['player_id']) for player in players}
    relevant = [row for player_id, row in rows.items() if player_id in ids]
    chinese = {str(row['player_id']) for row in relevant
               if re.search(r'[\u3400-\u9fff]', row.get('chinese_name') or '')}
    return {
        'season': registry.get('season', '2026-27'),
        'schema_version': registry.get('schema_version', 1),
        'salary_player_count': len(ids),
        'english_canonical_coverage': len(ids),
        'indexed_player_count': len(relevant),
        'chinese_name_count': len(chinese),
        'players_with_aliases': sum(bool(row.get('aliases')) for row in relevant),
        'alias_count': sum(len(row.get('aliases', [])) for row in relevant),
        'missing_index_player_ids': sorted(ids - rows.keys()),
        'missing_chinese_names': [
            {'player_id': str(player['player_id']), 'player': player['player']}
            for player in players if str(player['player_id']) not in chinese
        ],
    }


def _english_tokens(name):
    return [clean(word) for word in re.findall(r"[\w]+(?:['’\-][\w]+)*", name)
            if clean(word) not in _SUFFIXES]


@lru_cache(maxsize=8)
def _compiled_indexes(canonical_names, registered_names):
    exact = {}
    english_parts = {}

    def add(index, name, player_id):
        key = clean(name)
        if key:
            index.setdefault(key, set()).add(player_id)

    for player_id, name in canonical_names:
        add(exact, name, player_id)
        unsuffixed = re.sub(r'(?:[\s,.]+)(?:Jr\.?|Sr\.?|II|III|IV|V)$', '', name, flags=re.IGNORECASE)
        add(exact, unsuffixed, player_id)
        for token in _english_tokens(name):
            add(english_parts, token, player_id)
    for player_id, names in registered_names:
        for name in names:
            add(exact, name, player_id)
    return exact, english_parts


def _lookup_indexes(players):
    """Build exact aliases and conservative English token matches by ID."""
    by_id = {str(player['player_id']): player for player in players}
    canonical_names = tuple((player_id, player['player']) for player_id, player in by_id.items())
    registry = name_registry()
    registered_names = [
        (str(row['player_id']), tuple(_names_for_record(row)))
        for row in registry.get('players', []) if str(row['player_id']) in by_id]
    # Older season queries may contain players with no current salary record.
    # Match their archived aliases only to the exact original English target.
    by_english = {}
    for player_id, name in canonical_names:
        by_english.setdefault(clean(name), []).append(player_id)
    archived = registry.get('metadata', {}).get('unmatched_legacy_aliases', {})
    for alias, english_name in archived.items():
        for player_id in by_english.get(clean(english_name), []):
            registered_names.append((player_id, (alias,)))
    exact, english_parts = _compiled_indexes(canonical_names, tuple(registered_names))
    return by_id, exact, english_parts


def _query_name(query, recognized=()):
    key = clean(query)
    recognized = set(recognized)
    if key in recognized:
        return key
    words = sorted({clean(word) for word in (*TEAM_NAMES, *QUERY_WORDS)},
                   key=lambda word: (-len(word), word))
    # Both edges may contain query text. Explore their possible removal orders:
    # greedily removing 查 from 查尔斯 while a trailing 的 remains would destroy
    # a valid full name. Recognized names are terminals and never stripped.
    pending = [key]
    visited = {key}
    candidates = set()
    while pending:
        current = pending.pop()
        for word in words:
            next_keys = []
            if current.startswith(word):
                next_keys.append(current[len(word):])
            if current.endswith(word):
                next_keys.append(current[:-len(word)])
            for remainder in next_keys:
                if remainder in recognized:
                    candidates.add(remainder)
                elif remainder and remainder not in visited and len(visited) < 2048:
                    visited.add(remainder)
                    pending.append(remainder)
    # Prefer the longest complete known name; never search inside an unknown
    # residual name for a convenient shorter surname.
    return max(candidates, key=lambda name: (len(name), name)) if candidates else key


def _surname_matches(name, patterns):
    words = re.findall(r"[\w'-]+", name, flags=re.UNICODE)
    while words and clean(words[-1]) in _SUFFIXES:
        words.pop()
    surname = words[-1] if words else ''
    pieces = {clean(part) for part in re.split(r"[-']", surname)} | {clean(surname)}
    return bool(pieces & {clean(pattern) for pattern in patterns})


def _team_disambiguate(matches, query):
    team = mentioned_team(query)
    if not team or len(matches) <= 1:
        return matches
    narrowed = [player for player in matches if player.get('team') == team or
                team in player.get('teams_in_active_roster_sections', [])]
    return narrowed if len(narrowed) == 1 else matches


def _resolved_key(players, query):
    by_id, exact, english_parts = _lookup_indexes(players)
    ambiguous = {clean(name): surnames for name, surnames in AMBIGUOUS.items()}
    for surnames in AMBIGUOUS.values():
        for surname in surnames:
            ambiguous.setdefault(clean(surname), [surname])
    recognized = exact.keys() | english_parts.keys() | ambiguous.keys()
    return _query_name(query, recognized), by_id, exact, english_parts, ambiguous


def resolve(players, query):
    query = str(query).strip()
    by_id = {str(player['player_id']): player for player in players}
    if query in by_id:
        return [by_id[query]]
    key, by_id, exact, english_parts, ambiguous = _resolved_key(players, query)
    if key in ambiguous:
        # A Chinese surname can represent more than one English spelling
        # (for example 波特 = Porter/Potter). Preserve every registered target.
        registered_ids = exact.get(key, set())
        return _team_disambiguate(
            [player for player in players if str(player['player_id']) in registered_ids or
             _surname_matches(player['player'], ambiguous[key])], query)
    ids = exact.get(key)
    if ids is None:
        # Match complete English tokens, never arbitrary fragments such as
        # "Ant" or the recognized surname inside an unknown Chinese full name.
        ids = english_parts.get(key, set())
    matches = [player for player in players if str(player['player_id']) in ids]
    return _team_disambiguate(matches, query)


def mentioned_team(query):
    for name, code in sorted(TEAM_NAMES.items(), key=lambda item: len(item[0]), reverse=True):
        if name in query:
            return code
    return None


def requires_clarification(players, query, matches):
    """A surname stays ambiguous when only one namesake has cached salary."""
    key, _, _, _, ambiguous = _resolved_key(players, query)
    if key not in ambiguous:
        return False
    team = mentioned_team(query)
    return not (team and len(matches) == 1 and
                (matches[0].get('team') == team or
                 team in matches[0].get('teams_in_active_roster_sections', [])))
