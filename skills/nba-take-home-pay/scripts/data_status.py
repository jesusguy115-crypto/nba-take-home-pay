"""Content-addressed input versions, derived schedule coverage and change reports."""
from collections import Counter
import hashlib
import json
from pathlib import Path

from duty_days import TEAMS

CATEGORY_FILES = {
    'salary': ('assets/salaries-2026-27.json', 'assets/salaries-2025-26.json'),
    'schedule': ('assets/schedule-2026-27.json',),
    'profiles': ('assets/player-tax-profiles-2026-27.json',),
    'tax_rules': ('scripts/tax_east.py', 'scripts/tax_west.py', 'scripts/tax_federal.py',
                  'scripts/tax-east.json', 'scripts/tax-west.json', 'scripts/tax-federal-crossborder.json'),
    'settlement_rules': ('scripts/escrow-rules.json',),
    'model': ('scripts/estimate.py', 'scripts/duty_days.py', 'scripts/state_labels.py',
              'scripts/data_status.py', 'scripts/build_estimates.py', 'scripts/escrow.py'),
}


def input_file_paths(root):
    return [Path(root) / name for names in CATEGORY_FILES.values() for name in names]


def data_versions(root, model_version):
    """A content version changes on any byte change; as_of retains source dates."""
    versions = {}
    for category, names in CATEGORY_FILES.items():
        digest = hashlib.sha256()
        files = []
        for name in names:
            raw = (Path(root) / name).read_bytes()
            checksum = hashlib.sha256(raw).hexdigest()
            digest.update(name.encode('utf-8') + b'\0' + raw + b'\0')
            item = {'path': name, 'sha256': checksum}
            if name.endswith('.json'):
                obj = json.loads(raw)
                item['as_of'] = next((obj[key] for key in
                    ('captured_date', 'as_of', 'checked_date', 'checked_at', 'research_date')
                    if obj.get(key)), None)
                item['schema_version'] = obj.get('schema_version')
            files.append(item)
        dates = sorted({f['as_of'] for f in files if f.get('as_of')})
        checksum = digest.hexdigest()
        versions[category] = {
            'version': 'sha256:' + checksum[:16], 'sha256': checksum,
            'as_of': min(dates) if dates else None,
            'as_of_policy': 'earliest_source_review_date;see_each_file_for_dates',
            'files': files,
        }
        if category == 'model':
            versions[category]['model_version'] = model_version
            versions[category]['as_of_policy'] = 'not_a_source_snapshot;content_version_only'
    return versions


def schedule_coverage(schedule):
    """Recount actual assigned games; never copy stale summary fields."""
    known = Counter({team: 0 for team in TEAMS})
    ids = set()
    for game in schedule['games']:
        game_id = game['game_id']
        if game_id in ids:
            raise ValueError('Duplicate assigned game id: ' + str(game_id))
        ids.add(game_id)
        home, away = game['home'], game['away']
        if home not in TEAMS or away not in TEAMS or home == away:
            raise ValueError('Unsupported or identical teams in assigned game: ' + str(game_id))
        known.update((home, away))
    # This skill is specifically the NBA 2026–27 regular season: 30 teams, 82 games.
    expected_per_team = 82
    if any(count > expected_per_team for count in known.values()):
        raise ValueError('Assigned games exceed the 82-game regular-season limit')
    missing = {team: expected_per_team - known[team] for team in sorted(TEAMS)}
    expected = len(TEAMS) * expected_per_team // 2
    unassigned = expected - len(ids)
    placeholders = schedule.get('unassigned_games', [])
    placeholder_ids = [row['game_id'] for row in placeholders]
    if len(set(placeholder_ids)) != len(placeholder_ids) or ids.intersection(placeholder_ids):
        raise ValueError('Duplicate assigned/unassigned game ids')
    if len(placeholders) > unassigned:
        raise ValueError('Unassigned placeholders exceed remaining regular-season games')
    return {
        'known_regular_season_games': len(ids),
        'expected_regular_season_games': expected,
        'expected_games_per_team': expected_per_team,
        'unassigned_regular_games': unassigned,
        'known_games_per_team': dict(sorted(known.items())),
        'unassigned_games_per_team': missing,
        'published_unassigned_games': len(placeholders),
        'additional_games_not_listed': unassigned - len(placeholders),
        'basis': 'recount_games_and_unassigned_games;30_NBA_teams_times_82_divided_by_2',
    }


def schedule_uncertainty(schedule, team):
    coverage = schedule_coverage(schedule)
    count = coverage['unassigned_games_per_team'][team]
    if count:
        return (f'{TEAMS[team][0]}仍有{count}场常规赛未定；全联盟尚有'
                f'{coverage["unassigned_regular_games"]}场未定。这些日期按普通日历间隔估算，'
                '未编造对手、杯赛决赛或奖金。')
    return '本队82场常规赛均已确定；比赛表不证明球员实际随队履职，个人工作日仍采用模型假设。'


def amount_change(before, after):
    return {'before_usd': before, 'after_usd': after,
            'delta_usd': round(after - before, 2) if before is not None and after is not None else None}


def build_update_report(old_cache, new_cache):
    """Compare outputs and recorded inputs without claiming causal attribution."""
    old_cache = old_cache or {}
    old_versions = old_cache.get('data_versions', {})
    new_versions = new_cache['data_versions']
    version_changes = {}
    for category, new in new_versions.items():
        old = old_versions.get(category)
        status = ('changed' if old['sha256'] != new['sha256'] else 'unchanged') if old else 'previous_version_unknown'
        version_changes[category] = {'status': status, 'before': old, 'after': new}
    changed_categories = [key for key, value in version_changes.items() if value['status'] == 'changed']
    before = {str(p['player_id']): p for p in old_cache.get('estimates', [])}
    after = {str(p['player_id']): p for p in new_cache['estimates']}
    changes = []
    for player_id in sorted(before.keys() | after.keys()):
        old, new = before.get(player_id), after.get(player_id)
        current = new or old
        reasons = []
        if old is None:
            reasons.append('player_added')
        elif new is None:
            reasons.append('player_removed')
        else:
            observed = {
                'salary_changed': 'spotrac_salary_usd',
                'prior_season_salary_changed': 'previous_season_gross_usd',
                'team_changed': 'team', 'payment_teams_changed': 'paying_teams',
                'active_roster_status_changed': 'active_roster', 'profile_evidence_changed': 'tax_profile',
                'settlement_assumptions_changed': 'escrow_scenario',
            }
            reasons.extend(label for label, key in observed.items() if old.get(key) != new.get(key))
            if old.get('filing_scenario', {}).get('status') != new.get('filing_scenario', {}).get('status'):
                reasons.append('default_filing_scenario_changed')
        money = {key: amount_change(old.get(key) if old else None, new.get(key) if new else None)
                 for key in ('spotrac_salary_usd', 'gross_usd', 'estimated_net_usd', 'estimated_tax_usd')}
        old_variants = old.get('filing_scenarios', {}) if old else {}
        new_variants = new.get('filing_scenarios', {}) if new else {}
        variants = {}
        for status in sorted(old_variants.keys() | new_variants.keys()):
            a, b = old_variants.get(status), new_variants.get(status)
            if (a or {}).get('estimated_net_usd') != (b or {}).get('estimated_net_usd'):
                variants[status] = amount_change(a.get('estimated_net_usd') if a else None,
                                                b.get('estimated_net_usd') if b else None)
        old_components = old.get('components_usd', {}) if old else {}
        new_components = new.get('components_usd', {}) if new else {}
        components = {key: amount_change(old_components.get(key), new_components.get(key))
                      for key in sorted(old_components.keys() | new_components.keys())
                      if old_components.get(key) != new_components.get(key)}
        money_changed = any(value['before_usd'] != value['after_usd'] for value in money.values())
        if not (reasons or money_changed or variants or components):
            continue
        if money_changed or variants or components:
            reasons.append('calculated_amounts_changed')
        changes.append({
            'player_id': current['player_id'], 'player': current['player'],
            'team_before': old.get('team') if old else None, 'team_after': new.get('team') if new else None,
            'observed_changes': reasons, 'amounts': money, 'filing_scenario_net_changes': variants,
            'component_changes': components,
            'shared_inputs_changed': changed_categories,
        })
    record = {
        'schema_version': 1, 'season': new_cache['season'],
        'generated_at_utc': new_cache['generated_at_utc'],
        'comparison_status': ('no_prior_cache' if not old_cache else
                              'legacy_cache_without_category_versions' if not old_versions else 'versioned_comparison'),
        'before_model_fingerprint': old_cache.get('model_fingerprint'),
        'after_model_fingerprint': new_cache['model_fingerprint'],
        'input_versions': version_changes,
        'schedule_coverage_before': old_cache.get('schedule_coverage'),
        'schedule_coverage_after': new_cache['schedule_coverage'],
        'player_change_count': len(changes), 'player_changes': changes,
        'reason_policy': ('Observed input/output differences only. Shared changed inputs may affect a player; '
                          'this report does not decompose their individual causal dollar effects. '
                          'Missing historic versions are unknown, not inferred to be unchanged.'),
    }
    stable = {key: value for key, value in record.items() if key != 'generated_at_utc'}
    record['report_id'] = hashlib.sha256(json.dumps(stable, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()
    return record


def write_json_atomic(path, obj):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(obj, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    temp.replace(path)


def save_update_report(assets, report):
    assets = Path(assets)
    latest = assets / 'update-report-2026-27.json'
    history_path = assets / 'update-history-2026-27.json'
    history = json.loads(history_path.read_text(encoding='utf-8')) if history_path.exists() else {
        'schema_version': 1, 'season': report['season'], 'reports': []}
    changed = (report['player_change_count'] or
               any(row['status'] != 'unchanged' for row in report['input_versions'].values()))
    if changed and all(row['report_id'] != report['report_id'] for row in history['reports']):
        history['reports'].append(report)
    write_json_atomic(latest, report)
    write_json_atomic(history_path, history)
    return latest
