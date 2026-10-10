"""Test --draft-year: curated mapping loading, filtering, error handling."""
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


def test_draft_year_2022_returns_results():
    r = run('--draft-year', '2022')
    assert r.returncode == 0, f'non-zero exit: {r.stdout[:200]} {r.stderr[:200]}'
    d = json.loads(r.stdout)
    assert d['query']['draft_year'] == 2022
    assert d['matched_count'] >= 10, f'expected >=10 for 2022, got {d["matched_count"]}'
    assert d['returned_count'] == d['matched_count']


def test_draft_year_2023_returns_results():
    r = run('--draft-year', '2023')
    assert r.returncode == 0
    d = json.loads(r.stdout)
    assert d['query']['draft_year'] == 2023
    assert d['matched_count'] >= 5


def test_draft_year_unknown_year_errors():
    r = run('--draft-year', '2025')
    assert r.returncode == 2
    body = r.stdout + r.stderr
    assert 'curated 映射中没有' in body or 'draft' in body.lower()


def test_draft_year_cannot_with_compare():
    r = run('--draft-year', '2022', '--compare', '库里', '杜兰特')
    assert r.returncode == 2
    assert '用于联盟或球队名单' in (r.stdout + r.stderr)


def test_draft_year_cannot_with_player():
    r = run('库里', '--draft-year', '2022')
    assert r.returncode == 2
    assert '用于联盟或球队名单' in (r.stdout + r.stderr)


def test_draft_year_rendering_in_query():
    r = run('--draft-year', '2024')
    assert r.returncode == 0
    d = json.loads(r.stdout)
    assert d['query']['draft_year'] == 2024


def test_draft_year_combination_with_team():
    r = run('--draft-year', '2022', '--team', 'OKC')
    assert r.returncode == 0
    d = json.loads(r.stdout)
    assert d['query']['draft_year'] == 2022


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
