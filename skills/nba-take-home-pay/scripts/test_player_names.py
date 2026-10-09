"""Behavior checks for the shared ID-based English/Chinese name registry."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import player_names
from player_names import clean, name_index_coverage, requires_clarification, resolve

ROOT = Path(__file__).resolve().parents[1]


class ResolverBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.players = [
            {'player_id': '1', 'player': 'Anthony Davis', 'team': 'WAS'},
            {'player_id': '2', 'player': 'Jayson Tatum', 'team': 'BOS'},
            {'player_id': '3', 'player': 'Giannis Antetokounmpo', 'team': 'MIA'},
            {'player_id': '4', 'player': 'PJ Washington', 'team': 'DAL'},
            {'player_id': '5', 'player': 'LaMelo Ball', 'team': 'MIN'},
            {'player_id': '6', 'player': 'Lonzo Ball', 'team': 'CHI'},
            {'player_id': '7', 'player': 'Michael Porter Jr.', 'team': 'BKN'},
            {'player_id': '8', 'player': 'Kevin Porter Jr.', 'team': 'MIL'},
            {'player_id': '9', 'player': 'Nikola Jokic', 'team': 'DEN'},
        ]
        self.registry = {'schema_version': 1, 'season': '2026-27', 'players': [
            {'player_id': '1', 'english_name': 'Anthony Davis', 'chinese_name': '安东尼·戴维斯',
             'aliases': ['安东尼·戴维斯', '浓眉', 'AD']},
            {'player_id': '2', 'english_name': 'Jayson Tatum', 'chinese_name': '杰森·塔图姆',
             'aliases': ['杰森·塔图姆', '塔图姆']},
            {'player_id': '3', 'english_name': 'Giannis Antetokounmpo', 'chinese_name': '扬尼斯·阿德托昆博',
             'aliases': ['字母哥']},
            {'player_id': '4', 'english_name': 'PJ Washington', 'chinese_name': 'PJ·华盛顿',
             'aliases': ['PJ·华盛顿']},
            {'player_id': '5', 'english_name': 'LaMelo Ball', 'chinese_name': '拉梅洛·鲍尔',
             'aliases': ['三球']},
            {'player_id': '6', 'english_name': 'Lonzo Ball', 'chinese_name': '朗佐·鲍尔',
             'aliases': ['大球']},
            {'player_id': '7', 'english_name': 'Michael Porter Jr.', 'chinese_name': '小迈克尔·波特',
             'aliases': ['小波特']},
            {'player_id': '8', 'english_name': 'Kevin Porter Jr.', 'chinese_name': '小凯文·波特',
             'aliases': ['小波特']},
        ]}
        self.registry_patch = patch.object(player_names, 'name_registry', return_value=self.registry)
        self.registry_patch.start()
        self.addCleanup(self.registry_patch.stop)

    def assertPlayer(self, query, expected):
        matches = resolve(self.players, query)
        self.assertEqual([row['player'] for row in matches], [expected], query)
        self.assertFalse(requires_clarification(self.players, query, matches), query)

    def test_reported_chinese_names_and_middle_dots(self):
        for separator in ['·', '・', '•', '‧', '.', ' ', '　', '']:
            self.assertPlayer('安东尼' + separator + '戴维斯', 'Anthony Davis')
            self.assertPlayer('杰森' + separator + '塔图姆', 'Jayson Tatum')
        for query, name in [('塔图姆', 'Jayson Tatum'), ('字母哥', 'Giannis Antetokounmpo'),
                            ('浓眉', 'Anthony Davis'), ('aD', 'Anthony Davis')]:
            self.assertPlayer(query, name)

    def test_natural_query_words_without_trial_and_error(self):
        for query in ['请问安东尼・戴维斯的2026-27赛季税后薪水是多少？',
                      '我现在要安东尼·戴维斯新赛季的实际到手薪水',
                      '帮我查一下安东尼戴维斯的税后薪资吧',
                      'What is Anthony Davis net salary?',
                      'Please Anthony Davis take-home pay',
                      'How much does Anthony Davis make after tax?']:
            self.assertPlayer(query, 'Anthony Davis')
        self.assertPlayer('波士顿凯尔特人的塔图姆下赛季实际收入呢', 'Jayson Tatum')

    def test_english_accents_case_punctuation_initials_and_suffix(self):
        self.assertPlayer('NIKOLA JOKIĆ', 'Nikola Jokic')
        self.assertPlayer('ａｎｔｈｏｎｙ　ｄａｖｉｓ', 'Anthony Davis')
        self.assertPlayer('P. J. Washington', 'PJ Washington')
        self.assertPlayer('Michael Porter', 'Michael Porter Jr.')
        self.assertPlayer('Michael Porter Jr', 'Michael Porter Jr.')
        self.assertPlayer('Jayson', 'Jayson Tatum')
        self.assertPlayer('Tatum', 'Jayson Tatum')
        self.assertPlayer('1', 'Anthony Davis')

    def test_known_name_is_preserved_before_query_or_team_removal(self):
        # 华盛顿 is a team city token, but it is also this player's surname.
        self.assertPlayer('PJ·华盛顿', 'PJ Washington')
        self.assertPlayer('请问PJ・华盛顿的实际到手薪水', 'PJ Washington')
        self.assertPlayer('PJ Washington', 'PJ Washington')
        self.assertPlayer('森林狼的拉梅洛鲍尔税后收入', 'LaMelo Ball')

    def test_ambiguous_surnames_and_duplicate_nicknames_are_not_silently_chosen(self):
        for query, expected in [('鲍尔的薪水', {'LaMelo Ball', 'Lonzo Ball'}),
                                ('Ball', {'LaMelo Ball', 'Lonzo Ball'}),
                                ('小波特', {'Michael Porter Jr.', 'Kevin Porter Jr.'})]:
            matches = resolve(self.players, query)
            self.assertEqual({row['player'] for row in matches}, expected)
        self.assertTrue(requires_clarification(self.players, '鲍尔', resolve(self.players, '鲍尔')))
        self.assertPlayer('森林狼的鲍尔', 'LaMelo Ball')
        one_ball = [row for row in self.players if row['player'] != 'Lonzo Ball']
        matches = resolve(one_ball, '鲍尔')
        self.assertEqual(len(matches), 1)
        self.assertTrue(requires_clarification(one_ball, '鲍尔', matches))
        self.assertTrue(requires_clarification(one_ball, 'Ball', resolve(one_ball, 'Ball')))

    def test_unknown_given_name_and_arbitrary_english_fragments_do_not_fallback(self):
        for query in ['假名字戴维斯', '查一下假的塔图姆的薪水', 'Unknown Tatum',
                      'Ant', 'ayson', 'avid', '皮埃尔鲍尔', 'Nobody Porter']:
            self.assertEqual(resolve(self.players, query), [], query)
        # The registered Lonzo nickname must never substitute LaMelo if absent.
        one_ball = [row for row in self.players if row['player'] != 'Lonzo Ball']
        self.assertEqual(resolve(one_ball, '朗佐·鲍尔'), [])
        self.assertEqual(resolve(one_ball, '大球'), [])

    def test_registry_uses_stable_ids_and_does_not_add_absent_players(self):
        # Aliases remain valid when the salary vendor changes English spelling.
        renamed = [dict(row, player='P.J. Washington') if row['player_id'] == '4' else row
                   for row in self.players]
        self.assertEqual(resolve(renamed, 'PJ华盛顿')[0]['player_id'], '4')
        without_davis = [row for row in self.players if row['player_id'] != '1']
        self.assertEqual(resolve(without_davis, '浓眉'), [])

    def test_missing_registry_still_has_canonical_english_names(self):
        with patch.object(player_names, 'name_registry', return_value={'players': []}):
            self.assertPlayer('Anthony Davis', 'Anthony Davis')
            self.assertEqual(resolve(self.players, '浓眉'), [])

    def test_archived_aliases_only_match_their_original_english_target(self):
        self.registry['metadata'] = {'unmatched_legacy_aliases': {'威少': 'Russell Westbrook'}}
        self.assertEqual(resolve(self.players, '威少'), [])
        older = self.players + [{'player_id': '10', 'player': 'Russell Westbrook', 'team': 'DEN'}]
        self.assertEqual([row['player'] for row in resolve(older, '威少')], ['Russell Westbrook'])
        wrong = self.players + [{'player_id': '11', 'player': 'DAngelo Russell', 'team': 'BKN'}]
        self.assertEqual(resolve(wrong, '威少'), [])

    def test_coverage_uses_actual_salary_ids(self):
        summary = name_index_coverage(self.players)
        self.assertEqual(summary['english_canonical_coverage'], 9)
        self.assertEqual(summary['indexed_player_count'], 8)
        self.assertEqual(summary['chinese_name_count'], 8)
        self.assertEqual(summary['missing_index_player_ids'], ['9'])
        self.assertEqual(summary['missing_chinese_names'], [{'player_id': '9', 'player': 'Nikola Jokic'}])


class PublishedRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.players = json.loads((ROOT / 'assets/salaries-2026-27.json').read_text(encoding='utf-8'))['players']
        cls.registry = player_names.name_registry()

    def test_registry_covers_every_canonical_english_name(self):
        self.assertEqual({str(row['player_id']) for row in self.registry['players']},
                         {str(row['player_id']) for row in self.players})
        for player in self.players:
            matches = resolve(self.players, player['player'])
            self.assertEqual([str(row['player_id']) for row in matches], [str(player['player_id'])], player['player'])

    def test_user_reported_queries_use_real_installed_registry(self):
        for query, expected in [('安东尼・戴维斯', 'Anthony Davis'), ('浓眉', 'Anthony Davis'),
                                ('杰森·塔图姆', 'Jayson Tatum'), ('塔图姆', 'Jayson Tatum'),
                                ('字母哥', 'Giannis Antetokounmpo'), ('AD', 'Anthony Davis'),
                                ('浓眉哥', 'Anthony Davis'), ('獭兔', 'Jayson Tatum'),
                                ('杰森・塔特姆', 'Jayson Tatum'), ('JaysonTatum', 'Jayson Tatum')]:
            self.assertEqual([row['player'] for row in resolve(self.players, query)], [expected], query)

    def test_all_query_entry_points_share_the_same_chinese_name_index(self):
        from lookup_2026_27 import lookup
        from query_cache import lookup_player
        from take_home import match_error
        for query in ['安东尼・戴维斯', '杰森・塔图姆', '塔图姆', '獭兔', 'AD']:
            expected = str(resolve(self.players, query)[0]['player_id'])
            primary, error = match_error(self.players, query)
            self.assertIsNone(error, query)
            self.assertEqual(str(primary['player_id']), expected, query)
            for result in [lookup_player('2026-27', query), lookup(query)]:
                self.assertEqual(str(result.get('spotrac_player_id')), expected, query)

    def test_chinese_full_names_work_inside_normal_salary_questions(self):
        for row in self.registry['players']:
            query = '请问' + row['chinese_name'].replace('·', '・') + '的新赛季税后到手薪水是多少？'
            matches = resolve(self.players, query)
            self.assertIn(str(row['player_id']), [str(match['player_id']) for match in matches], query)

    def test_registered_names_are_resolvable_or_intentionally_ambiguous(self):
        for row in self.registry['players']:
            for name in player_names._names_for_record(row):
                matches = resolve(self.players, name)
                self.assertIn(str(row['player_id']), [str(match['player_id']) for match in matches], name)


if __name__ == '__main__':
    unittest.main(verbosity=2)
