"""Offline age metadata and inclusive/exclusive filters, independent of tax math."""
from datetime import date
import json
from pathlib import Path

AGE_FILE = Path(__file__).resolve().parents[1] / 'assets/player-birthdates-2026-27.json'


def load_birthdates(path=AGE_FILE):
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('schema_version') != 1 or data.get('season') != '2026-27':
        raise ValueError('出生日期索引版本或赛季无效')
    result = {}
    for row in data['players']:
        identifier = row['player_id']
        if identifier in result:
            raise ValueError('出生日期索引球员 ID 重复：' + identifier)
        if row.get('birth_date'):
            date.fromisoformat(row['birth_date'])
        result[identifier] = row
    return result


def age_on(birth_date, as_of):
    born = date.fromisoformat(birth_date)
    if born > as_of:
        return None
    return as_of.year - born.year - ((as_of.month, as_of.day) < (born.month, born.day))


def age_metadata(player_id, birthdays, as_of):
    row = birthdays.get(str(player_id), {})
    born = row.get('birth_date')
    age = age_on(born, as_of) if born else None
    return {'age': age, 'birth_date': born, 'age_as_of': as_of.isoformat(),
            'age_status': 'known' if age is not None else 'not_born_on_date' if born else 'unknown',
            'age_source': row.get('source'), 'birth_date_checked': row.get('checked_date')}


def filter_by_age(selected, birthdays, as_of, minimum=None, maximum=None, under=None, birth_year_min=None, birth_year_max=None):
    """Filter before ranking. Missing DOB cannot silently produce an incomplete Top N."""
    result, missing = [], []
    for row, query in selected:
        info = age_metadata(row['player_id'], birthdays, as_of)
        age = info['age']
        if age is None:
            missing.append(row['player'])
        elif ((minimum is None or age >= minimum) and (maximum is None or age <= maximum) and
              (under is None or age < under) and
              (birth_year_min is None or int(info['birth_date'][:4]) >= birth_year_min) and
              (birth_year_max is None or int(info['birth_date'][:4]) <= birth_year_max)):
            result.append((row, query))
    if missing:
        raise ValueError('年龄筛选范围中有未核实出生日期或尚未出生的球员，不能给出完整排名：' + '、'.join(missing))
    return result


def age_coverage(players, birthdays, as_of):
    missing = [p['player'] for p in players if age_metadata(p['player_id'], birthdays, as_of)['age'] is None]
    return {'age_as_of': as_of.isoformat(), 'player_count': len(players),
            'known_age_count': len(players) - len(missing), 'missing_players': missing,
            'basis': 'completed_years_on_age_as_of; local_system_date_by_default'}
