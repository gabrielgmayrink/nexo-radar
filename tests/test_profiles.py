import unittest
from unittest.mock import patch
import json
from radar.profiles import load_profiles


class ProfileTests(unittest.TestCase):
    def test_new_companies_have_no_assumed_services(self):
        companies=load_profiles()
        self.assertEqual([company['name'] for company in companies],['Daltton','Gerico'])
        self.assertTrue(all(not company['enabled'] and not company['terms'] and not company['services'] for company in companies))

    def test_enabling_incomplete_profile_is_rejected(self):
        companies=load_profiles()
        companies[0]['enabled']=True
        with patch('pathlib.Path.read_text',return_value=json.dumps({'companies':companies})):
            with self.assertRaises(ValueError):load_profiles()
