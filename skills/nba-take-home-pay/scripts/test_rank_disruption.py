"""Test --rank-disruption: full two-pass sort, delta computation, boundary label."""
import subprocess
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAKE_HOME = ROOT / 'scripts' / 'take_home.py'


def run(*args):
    result = subprocess.run(
        [sys.executable, '-X', 'utf8', str(TAKE_HOME), '--json', '--brief', *args],
        capture_output=True, text=True, cwd=str(ROOT), timeout=60,
    )
    return result


def test_rank_disruption_json_shape():
    r = run('--rank-disruption', '--top', '5')
    assert r.returncode == 0, f'non-zero exit: {r.stderr[:200]}'
    d = json.loads(r.stdout)
    assert d['query']['kind'] == 'rank_disruption', d['query']['kind']
    assert d['query']['sort'] == 'rank_disruption'
    assert '不是换队因果推断' in d['query']['ranking_note']
    rs = d['results']
    assert len(rs) == 10, f'expected up/down 5 each, got {len(rs)}'
    for row in rs:
        assert row.get('gross_rank') is not None, f'missing gross_rank: {row}'
        assert row.get('net_rank') is not None, f'missing net_rank: {row}'
        assert row.get('rank_delta') is not None, f'missing rank_delta: {row}'


def test_rank_disruption_up_and_down():
    r = run('--rank-disruption', '--top', '3')
    d = json.loads(r.stdout)
    rs = d['results']
    deltas = [row['rank_delta'] for row in rs]
    # First should be positive (up movers), last should be negative (down movers)
    assert deltas[0] > 0, f'first row should be up mover, got delta={deltas[0]}'
    assert deltas[-1] < 0, f'last row should be down mover, got delta={deltas[-1]}'


def test_rank_disruption_cannot_with_compare():
    r = run('--rank-disruption', '--compare', '库里', '杜兰特')
    assert r.returncode == 2
    assert '不能与单人姓名或 --compare' in (r.stdout + r.stderr)


def test_rank_disruption_cannot_with_sort():
    r = run('--rank-disruption', '--sort', 'gross')
    assert r.returncode == 2
    assert '不需要 --sort' in (r.stdout + r.stderr)


def test_rank_disruption_all_520_computed():
    r = run('--rank-disruption', '--top', '10')
    d = json.loads(r.stdout)
    assert d['matched_count'] >= 500, f'expected >=500 matched, got {d["matched_count"]}'


def test_top_does_not_shrink_rank_population():
    full=json.loads(run('--rank-disruption').stdout)
    small=json.loads(run('--rank-disruption','--top','3').stdout)
    assert len(small['results'])==6
    assert small['query']['rank_population']==520
    expected={r['player_id']:(r['gross_rank'],r['net_rank']) for r in full['results']}
    for r in small['results']:
        assert (r['gross_rank'],r['net_rank'])==expected[r['player_id']]
        assert r['rank_delta']!=0
    assert max(r['gross_rank'] for r in small['results'])>3

if __name__ == '__main__':
    tests = [v for k, v in globals().items() if k.startswith('test_')]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f'PASS {t.__name__}')
            passed += 1
        except Exception as e:
            print(f'FAIL {t.__name__}: {e}')
            failed += 1
    print(f'\n{passed} passed, {failed} failed')
    sys.exit(0 if failed == 0 else 1)
