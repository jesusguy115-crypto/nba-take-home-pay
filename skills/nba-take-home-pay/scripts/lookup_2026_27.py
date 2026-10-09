#!/usr/bin/env python3
"""Backward-compatible entry point; reads the current JSON cache."""
import argparse
import json
from query_cache import lookup_player, schedule_summary


def lookup(query, include_games=False):
    result = lookup_player("2026-27", query)
    teams = result.get("teams_in_active_roster_sections", [])
    if len(teams) == 1:
        result["team"] = teams[0]
        result["team_schedule"] = schedule_summary("2026-27", teams[0], include_games)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("player")
    parser.add_argument("--games", action="store_true")
    args = parser.parse_args()
    print(json.dumps(lookup(args.player, args.games), ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
