import unittest
from radar.search import parse_query,matches_query


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.row={'object':'Serviços de tecnologia da informação e desenvolvimento de sistemas',
                  'additionalInfo':'Capacitação por ensino a distância','organization':'Prefeitura de São João',
                  'city':'Belo Horizonte','state':'MG','id':'12345678000100-1-000001/2026'}

    def test_words_accents_state_and_control_number(self):
        for query in ('SISTEMAS horizonte','capacitação JOÃO','MG','000001/2026'):
            self.assertTrue(matches_query(self.row,parse_query(query)),query)

    def test_exact_phrases_and_exclusions(self):
        self.assertTrue(matches_query(self.row,parse_query('"desenvolvimento de sistemas" -equipamentos')))
        self.assertFalse(matches_query(self.row,parse_query('"sistemas desenvolvimento"')))
        self.assertFalse(matches_query(self.row,parse_query('sistemas -"tecnologia da informação"')))

    def test_acronyms_do_not_match_incidental_fragments(self):
        self.assertTrue(matches_query(self.row,parse_query('TI EAD')))
        self.assertFalse(matches_query({'object':'Atividades sociais'},parse_query('TI')))

    def test_negative_only_and_incomplete_quotes_are_safe(self):
        self.assertTrue(matches_query(self.row,parse_query('-equipamentos')))
        self.assertTrue(matches_query(self.row,parse_query('"sistemas')))
        self.assertFalse(matches_query(self.row,parse_query('-sistemas')))
