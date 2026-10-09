"""Chart output contracts: source fidelity, offline safety and query membership."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import render_chart
import take_home


class ChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.command = [sys.executable, '-B', '-X', 'utf8', str(Path(__file__).with_name('take_home.py'))]
        cls.args = ['--min-age', '35', '--top', '10', '--sort', 'net', '--order', 'asc', '--age-date', '2026-10-10', '--brief', '--json']
        cls.payload = json.loads(subprocess.check_output(cls.command + cls.args, text=True))

    def test_lowest_net_filters_before_limit(self):
        all_rows = json.loads(subprocess.check_output(self.command + ['--top', '520', '--sort', 'net', '--order', 'asc', '--age-date', '2026-10-10', '--brief', '--json'], text=True))['results']
        expected = [r['player_id'] for r in all_rows if r['age'] >= 35][:10]
        self.assertEqual([r['player_id'] for r in self.payload['results']], expected)
        self.assertEqual(self.payload['query']['order'], 'asc')

    def test_chart_does_not_change_query_and_sidecars_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / '薪水 图.html'
            result = json.loads(subprocess.check_output(self.command + self.args + ['--chart', str(path)], text=True))
            result.pop('visualization')
            self.assertEqual(result, self.payload)
            self.assertEqual(json.loads(path.with_suffix('.json').read_text()), result)
            self.assertEqual(path.with_suffix('.md').read_text(), render_chart.table_markdown(render_chart.chart_data(result)))
            text = path.read_text()
            self.assertNotIn('__DATA_JSON__', text)
            self.assertNotIn('__CJK_FONT__', text)
            self.assertIn('data:font/woff2;base64,', text)
            self.assertIn('SIL OPEN FONT LICENSE', text)
            self.assertNotIn('<script src=', text)

    def test_renderer_does_not_mutate_input(self):
        before = deepcopy(self.payload)
        with tempfile.TemporaryDirectory() as tmp:
            render_chart.write_chart(self.payload, Path(tmp) / 'result.html')
        self.assertEqual(self.payload, before)

    def test_labels_dates_and_amounts_are_preserved(self):
        data = render_chart.chart_data(self.payload)
        self.assertEqual(data['ageDate'], '2026-10-10')
        for source, row in zip(self.payload['results'], data['rows']):
            self.assertEqual(source['estimated_net_usd'], row['net'])
            self.assertEqual(source['spotrac_salary_usd'], row['gross'])
            self.assertEqual(source['roster_status_label'], row['status'])
        markdown = render_chart.table_markdown(data)
        self.assertIn('非现役·保留付款', markdown)
        self.assertIn('免税州', markdown)
        self.assertIn('5.48%', markdown)

    def test_single_and_empty_are_supported(self):
        single = self.payload['results'][0]
        self.assertEqual(len(render_chart.chart_data(single)['rows']), 1)
        empty = deepcopy(self.payload)
        empty['results'] = []
        self.assertEqual(render_chart.chart_data(empty)['rows'], [])

    def test_untrusted_text_cannot_close_script(self):
        payload = deepcopy(self.payload)
        payload['results'][0]['player_id'] = 'unknown'
        payload['results'][0]['player'] = '</script><img src=x onerror=alert(1)>'
        payload['results'][0]['sources']['salary'] = 'javascript:alert(1)'
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'result.html'
            render_chart.write_chart(payload, path)
            text = path.read_text()
        self.assertNotIn('</script><img', text)
        self.assertNotIn('javascript:alert', text)
        self.assertIn('\\u003c/script\\u003e', text)

    def test_nonfinite_and_duplicate_rows_rejected(self):
        payload = deepcopy(self.payload)
        payload['results'][0]['estimated_net_usd'] = float('nan')
        with self.assertRaises(ValueError):
            render_chart.chart_data(payload)
        payload = deepcopy(self.payload)
        payload['results'].append(payload['results'][0])
        with self.assertRaises(ValueError):
            render_chart.chart_data(payload)

    def test_lowest_gross_uses_ascending_preselection(self):
        result = json.loads(subprocess.check_output(self.command + ['--top', '5', '--sort', 'gross', '--order', 'asc', '--brief', '--json'], text=True))
        salaries = json.loads((render_chart.ROOT / 'assets/net-estimates-2026-27.json').read_text())['estimates']
        # The public query returns all payroll records by default.
        expected = sorted(r['spotrac_salary_usd'] for r in salaries)[:5]
        self.assertEqual([r['spotrac_salary_usd'] for r in result['results']], expected)


if __name__ == '__main__':
    unittest.main()
