#!/usr/bin/env python3
"""Offline salary and regular-season schedule lookup. Python standard library only."""
import argparse
import json
from collections import Counter
from pathlib import Path
from player_names import resolve, requires_clarification, TEAM_NAMES

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
TEAM_ALIASES = TEAM_NAMES

def load_json(name):
    return json.loads((ASSETS / name).read_text())

def find_players(players, query):
    return resolve(players, query)

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
    if len(matches) != 1 or requires_clarification(data["players"], query, matches):
        return {"status": "ambiguous" if matches else "not_found", "season": season, "query": query, "match_count": len(matches),
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
