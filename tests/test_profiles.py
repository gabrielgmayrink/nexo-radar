import unittest
from unittest.mock import patch
import json
from radar.profiles import load_profiles


class ProfileTests(unittest.TestCase):
    def test_public_uses_confirmed_services_and_gerico_remains_pending(self):
        companies=load_profiles()
        self.assertEqual([company['name'] for company in companies],['Public','Gerico'])
        self.assertTrue(companies[0]['enabled'])
        self.assertIn('desenvolvimento de sistemas',companies[0]['terms'])
        self.assertFalse(companies[1]['enabled'])
        self.assertEqual(companies[1]['terms'],[])

    def test_enabling_incomplete_profile_is_rejected(self):
        companies=load_profiles()
        companies[1]['enabled']=True
        with patch('pathlib.Path.read_text',return_value=json.dumps({'companies':companies})):
            with self.assertRaises(ValueError):load_profiles()
