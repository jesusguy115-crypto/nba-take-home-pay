#!/usr/bin/env python3
"""Validate and install user-supplied NBA snapshots. Offline, Python 3.9+."""
import argparse
from datetime import date, datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid

REQUIRED = (
    "salaries-2026-27.json",
    "salaries-2025-26.json",
    "schedule-2026-27.json",
    "player-tax-profiles-2026-27.json",
)
CACHE = "net-estimates-2026-27.json"
HERE = Path(__file__).resolve().parent
DEFAULT_SKILL = HERE if (HERE / "SKILL.md").is_file() else HERE / "skills" / "nba-take-home-pay"


class ImportFailure(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ImportFailure(message)


def read_json(path):
    def invalid_constant(value):
        raise ImportFailure("Non-finite JSON number: " + value)
    try:
        data = json.loads(path.read_text(encoding="utf-8"), parse_constant=invalid_constant)
    except (OSError, ValueError) as exc:
        raise ImportFailure("Cannot read {}: {}".format(path.name, exc)) from exc
    require(isinstance(data, dict), path.name + " must contain a JSON object")
    return data


def fields(value, keys, context):
    require(isinstance(value, dict), context + " must be an object")
    missing = set(keys) - set(value)
    require(not missing, context + " missing keys: " + ", ".join(sorted(missing)))


def text_value(value, context, allow_empty=False):
    require(isinstance(value, str) and (allow_empty or bool(value.strip())), context + " must be a string")


def amount(value, context, nonnegative=True):
    require(type(value) in (int, float) and math.isfinite(value)
            and (not nonnegative or value >= 0), context + " must be a finite number" + (" >= 0" if nonnegative else ""))


def rows(value, context):
    require(isinstance(value, list) and bool(value), context + " must be a nonempty array")
    return value


def validate_inputs(assets, teams):
    current = read_json(assets / REQUIRED[0])
    previous = read_json(assets / REQUIRED[1])
    for season, salary in (("2026-27", current), ("2025-26", previous)):
        context = "salaries-" + season
        fields(salary, ("season", "captured_date", "currency", "players"), context)
        require(salary["season"] == season, context + " has the wrong season")
        require(salary["currency"] == "USD", context + " currency must be USD")
        date.fromisoformat(salary["captured_date"])
        seen = set()
        for player in rows(salary["players"], context + ".players"):
            fields(player, ("player_id", "cash_total_usd"), context + ".players[]")
            text_value(player["player_id"], context + ".player_id")
            require(player["player_id"] not in seen, context + " has duplicate player_id")
            seen.add(player["player_id"])
            amount(player["cash_total_usd"], context + ".cash_total_usd")

    fields(current, ("payment_records",), REQUIRED[0])
    records = {}
    for record in rows(current["payment_records"], "payment_records"):
        fields(record, ("record_id", "player_id", "team", "source_section", "cash_total_usd", "source_url"), "payment_records[]")
        for key in ("record_id", "player_id", "source_section", "source_url"):
            text_value(record[key], "payment_records[]." + key)
        require(record["record_id"] not in records, "Duplicate payment record_id")
        require(record["team"] in teams, "Unknown payment team: " + str(record["team"]))
        amount(record["cash_total_usd"], "payment_records[].cash_total_usd")
        records[record["record_id"]] = record
    payer_teams = set()
    for player in current["players"]:
        fields(player, ("player", "player_url", "paying_teams", "payment_record_ids"), "players[]")
        for key in ("player", "player_url"):
            text_value(player[key], "players[]." + key)
        payer_list = rows(player["paying_teams"], "players[].paying_teams")
        require(all(isinstance(team, str) and team in teams for team in payer_list), "Unknown paying_teams entry")
        links = rows(player["payment_record_ids"], "players[].payment_record_ids")
        require(all(isinstance(link, str) and link in records for link in links), "Unknown payment_record_ids entry")
        require(len(set(links)) == len(links), "Duplicate payment_record_ids entry")
        payments = [records[link] for link in links]
        require(all(r["player_id"] == player["player_id"] for r in payments), "Payment record belongs to another player")
        require(set(payer_list) == {r["team"] for r in payments}, "paying_teams does not match payment records")
        require(math.isclose(sum(r["cash_total_usd"] for r in payments), player["cash_total_usd"], abs_tol=0.01, rel_tol=0), "Player cash total does not match payment records")
        active = [r for r in payments if r["source_section"] == "Active Roster"]
        payer_teams.add(max(active or payments, key=lambda r: r["cash_total_usd"])["team"])

    schedule = read_json(assets / REQUIRED[2])
    fields(schedule, ("season", "source_url", "games"), REQUIRED[2])
    require(schedule["season"] == "2026-27", "Wrong schedule season")
    text_value(schedule["source_url"], "schedule.source_url")
    game_ids, team_dates, scheduled_teams = set(), set(), set()
    for game in rows(schedule["games"], "schedule.games"):
        fields(game, ("game_id", "date_et", "home", "away", "arena_country", "arena_state", "arena_city"), "games[]")
        for key in ("game_id", "date_et", "arena_country", "arena_city"):
            text_value(game[key], "games[]." + key)
        text_value(game["arena_state"], "games[].arena_state", allow_empty=True)
        day = date.fromisoformat(game["date_et"])
        require(date(2026, 9, 29) <= day <= date(2027, 4, 11), "Game is outside the modeled season window")
        require(game["game_id"] not in game_ids, "Duplicate game_id")
        game_ids.add(game["game_id"])
        require(game["home"] != game["away"], "A game must have different teams")
        for team in (game["home"], game["away"]):
            require(isinstance(team, str) and team in teams, "Unknown schedule team")
            require((team, game["date_et"]) not in team_dates, "Duplicate game date for " + team)
            team_dates.add((team, game["date_et"]))
            scheduled_teams.add(team)
    require(payer_teams <= scheduled_teams, "Schedule is missing a player's modeled team")

    profile_data = read_json(assets / REQUIRED[3])
    fields(profile_data, ("season", "profiles"), REQUIRED[3])
    require(profile_data["season"] == "2026-27", "Wrong profile season")
    require(isinstance(profile_data["profiles"], dict), "profiles must be keyed by player_id")
    for player in current["players"]:
        profile = profile_data["profiles"].get(player["player_id"])
        fields(profile, ("player_id", "marital_status", "actual_filing_status"), "profile " + player["player_id"])
        require(profile["player_id"] == player["player_id"], "Profile player_id mismatch")
        for key in ("marital_status", "actual_filing_status"):
            text_value(profile[key], "profiles[]." + key)
    return current


def run_model(stage, *arguments):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    result = subprocess.run([sys.executable, "-X", "utf8", *arguments], cwd=str(stage / "scripts"),
                            env=env, capture_output=True, text=True, encoding="utf-8", timeout=300)
    require(result.returncode == 0, "Model validation failed:\n" + (result.stderr or result.stdout)[-3000:])
    return result.stdout.strip()


def validate_cache(stage, salaries, fingerprint):
    cache = read_json(stage / "assets" / CACHE)
    fields(cache, ("season", "model_fingerprint", "count", "estimates"), CACHE)
    require(cache["season"] == "2026-27", "Wrong cache season")
    require(cache["model_fingerprint"] == fingerprint,
            "Cache fingerprint mismatch. Remove the stale cache from your source copy and re-import to rebuild it locally.")
    estimates = rows(cache["estimates"], "cache.estimates")
    ids = []
    for item in estimates:
        fields(item, ("player_id", "player", "team", "estimated_net_usd", "rounded_net_usd", "estimated_tax_usd", "components_usd", "filing_scenario", "filing_scenarios"), "cache.estimates[]")
        text_value(item["player_id"], "cache.player_id")
        for key in ("estimated_net_usd", "rounded_net_usd", "estimated_tax_usd"):
            amount(item[key], "cache." + key, nonnegative=False)
        require(isinstance(item["components_usd"], dict), "cache.components_usd must be an object")
        for value in item["components_usd"].values():
            amount(value, "cache.components_usd[]", nonnegative=False)
        ids.append(item["player_id"])
    expected_ids = {player["player_id"] for player in salaries["players"]}
    require(len(ids) == len(set(ids)) and set(ids) == expected_ids and cache["count"] == len(ids),
            "Cache player coverage or count does not match current salaries")
    # Exercise the public entry point and recompute one real player from inputs.
    player_id = salaries["players"][0]["player_id"]
    cached = json.loads(run_model(stage, "take_home.py", player_id, "--json"))
    calculated = json.loads(run_model(stage, "take_home.py", player_id, "--explain"))
    require(cached.get("player_id") == player_id and calculated.get("player_id") == player_id,
            "Validation query did not resolve the imported player")
    for key in ("estimated_net_usd", "rounded_net_usd", "estimated_tax_usd", "components_usd"):
        require(cached.get(key) == calculated.get(key), "Cache query differs from the current calculation: " + key)
    return len(ids), player_id


def import_data(source, skill_path, force=False):
    source, skill_path = Path(source).resolve(), Path(skill_path).resolve()
    require(source.is_dir(), "--source must be your existing assets directory")
    require((skill_path / "scripts" / "take_home.py").is_file(), "--skill-path must contain scripts/take_home.py")
    missing = [name for name in REQUIRED if not (source / name).is_file()]
    require(not missing, "Missing required data: " + ", ".join(missing))
    target = skill_path / "assets"
    require(not target.is_symlink(), "Refusing to replace a symlink at assets")
    require(not target.exists() or target.is_dir(), "Existing assets is not a directory")
    require(force or not target.exists() or not any(target.iterdir()),
            "Existing assets is not empty; use --force to replace it and retain a backup")
    with tempfile.TemporaryDirectory(prefix="." + skill_path.name + "-import-", dir=str(skill_path.parent)) as temporary:
        stage = Path(temporary)
        shutil.copytree(skill_path / "scripts", stage / "scripts", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (stage / "assets").mkdir()
        for name in REQUIRED + (CACHE,):
            if (source / name).is_file():
                shutil.copyfile(source / name, stage / "assets" / name)
        teams = json.loads(run_model(stage, "-c", "import json; from duty_days import TEAMS; print(json.dumps(list(TEAMS)))"))
        salaries = validate_inputs(stage / "assets", set(teams))
        rebuilt = not (stage / "assets" / CACHE).exists()
        if rebuilt:
            run_model(stage, "build_estimates.py")
        fingerprint = run_model(stage, "-c", "from estimate import model_fingerprint; print(model_fingerprint())")
        count, player_id = validate_cache(stage, salaries, fingerprint)
        # Recheck immediately before replacement. Each rename stays on the same filesystem.
        require(force or not target.exists() or not any(target.iterdir()), "Assets appeared during validation; rerun with --force")
        backup = None
        if target.exists():
            suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
            backup = skill_path / ("assets.backup-" + suffix)
            target.rename(backup)
        try:
            (stage / "assets").rename(target)
        except BaseException:
            if backup is not None and not target.exists():
                backup.rename(target)
            raise
    return {"assets": str(target), "backup": str(backup) if backup else None,
            "players": count, "verified_player_id": player_id, "cache_rebuilt": rebuilt}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="Existing assets directory you are entitled to use")
    parser.add_argument("--skill-path", type=Path, default=DEFAULT_SKILL, help="Target skill directory (defaults to this release)")
    parser.add_argument("--force", action="store_true", help="Replace existing assets after validation, retaining a timestamped backup")
    args = parser.parse_args(argv)
    try:
        result = import_data(args.source, args.skill_path, args.force)
    except (ImportFailure, OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        print("Import failed: " + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
