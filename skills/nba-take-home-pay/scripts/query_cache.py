#!/usr/bin/env python3
"""Offline salary and regular-season schedule lookup. Python standard library only."""
import argparse
import json
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ALIASES = {
    "库里": "Stephen Curry", "斯蒂芬库里": "Stephen Curry",
    "爱德华兹": "Anthony Edwards", "安东尼爱德华兹": "Anthony Edwards",
    "詹姆斯": "LeBron James", "勒布朗": "LeBron James", "勒布朗詹姆斯": "LeBron James",
    "杜兰特": "Kevin Durant", "东契奇": "Luka Doncic", "约基奇": "Nikola Jokic",
    "字母哥": "Giannis Antetokounmpo", "文班亚马": "Victor Wembanyama",
    "拉梅洛鲍尔": "LaMelo Ball", "拉梅洛": "LaMelo Ball", "三球": "LaMelo Ball",
    "朗佐鲍尔": "Lonzo Ball", "大球": "Lonzo Ball",
    "哈登": "James Harden", "加兰": "Darius Garland", "戴维斯": "Anthony Davis",
    "浓眉": "Anthony Davis", "恩比德": "Joel Embiid", "塔图姆": "Jayson Tatum",
    "杰伦布朗": "Jaylen Brown", "巴特勒": "Jimmy Butler", "布克": "Devin Booker",
    "戈贝尔": "Rudy Gobert", "康利": "Mike Conley", "唐斯": "Karl-Anthony Towns",
    "亚历山大": "Shai Gilgeous-Alexander", "米切尔": "Donovan Mitchell",
    "利拉德": "Damian Lillard", "欧文": "Kyrie Irving",
}
TEAM_ALIASES = {
    "森林狼": "MIN", "勇士": "GSW", "湖人": "LAL", "快船": "LAC", "黄蜂": "CHA",
    "骑士": "CLE", "凯尔特人": "BOS", "火箭": "HOU", "雷霆": "OKC",
    "掘金": "DEN", "马刺": "SAS", "雄鹿": "MIL", "独行侠": "DAL",
    "尼克斯": "NYK", "76人": "PHI", "猛龙": "TOR",
}

def clean(value):
    return "".join(c for c in unicodedata.normalize("NFKD", value).casefold() if c.isalnum())

def load_json(name):
    return json.loads((ASSETS / name).read_text())

def find_players(players, query):
    alias_keys = {clean(k): v for k, v in ALIASES.items()}
    query = alias_keys.get(clean(query), query.strip())
    key = clean(query)
    exact = [p for p in players if clean(p["player"]) == key or p["player_id"] == query]
    return exact or [p for p in players if key and key in clean(p["player"])]

def schedule_summary(season, team, include_games=False):
    team = TEAM_ALIASES.get(team, team.upper())
    data = load_json(f"schedule-{season}.json")
    all_games, captured, url = data["games"], data["captured_date"], data["source_url"]
    valid_teams = {t for g in all_games for t in (g["home"], g["away"])} - {"TBD", ""}
    if team not in valid_teams:
        return {"error": "Unknown team", "query": team, "available_teams": sorted(valid_teams)}
    games = [g for g in all_games if team in (g["home"], g["away"])]
    venues = Counter(f'{g["arena_country"]}:{g["arena_state"] or g["arena_city"]}' for g in games)
    result = {
        "season": season, "captured_date": captured, "team": team,
        "regular_season_games": len(games),
        "designated_home_games": sum(g["home"] == team for g in games),
        "designated_away_games": sum(g["away"] == team for g in games),
        "venue_game_counts": dict(sorted(venues.items())), "source_url": url,
        "note": "Team schedule only. Game counts are not player duty days; payer teams are not proof of where the player worked.",
    }
    if season == "2026-27":
        result["unassigned_regular_season_games"] = data["unassigned_games_per_team"][team]
    if include_games:
        result["games"] = games
    return result

def lookup_player(season, query):
    data = load_json(f"salaries-{season}.json")
    matches = find_players(data["players"], query)
    if len(matches) != 1:
        return {"season": season, "query": query, "match_count": len(matches),
                "matches": [{"player": p["player"], "player_id": p["player_id"],
                             "cash_total_usd": p["cash_total_usd"]} for p in matches]}
    player = matches[0]
    records_by_id = {r["record_id"]: r for r in data["payment_records"]}
    records = [records_by_id[rid] for rid in player["payment_record_ids"]]
    result = {
        "season": season, "captured_date": data["captured_date"],
        "player": player["player"], "spotrac_player_id": player["player_id"],
        "cash_total_usd": player["cash_total_usd"], "currency": "USD",
        "salary_basis": data["salary_basis"], "paying_teams": player["paying_teams"],
        "teams_in_active_roster_sections": player["teams_in_active_roster_sections"],
        "payment_records": records, "player_source_url": player["player_url"],
        "note": "Published cash snapshot as of captured_date; team categories belong to the selected season. Multiple contracts are preserved. No future transaction, tax or actual bank deposit is calculated.",
    }
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", required=True, choices=["2025-26", "2026-27"])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--player")
    mode.add_argument("--team")
    mode.add_argument("--coverage", action="store_true")
    parser.add_argument("--games", action="store_true", help="Include game rows with --team")
    args = parser.parse_args()
    if args.games and not args.team:
        parser.error("--games requires --team")
    if args.player:
        result = lookup_player(args.season, args.player)
    elif args.team:
        result = schedule_summary(args.season, args.team, args.games)
    else:
        result = load_json(f"coverage-{args.season}.json")
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))

if __name__ == "__main__":
    main()
