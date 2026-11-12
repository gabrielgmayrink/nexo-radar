import unittest
from copy import deepcopy
from unittest.mock import MagicMock,patch
from radar.company_profiles import validate_configuration,save_profile,ProfileConflict
from radar.company_access import AccessDenied
from radar.profiles import load_profiles,profile_context
from radar.relevance import classify,classification_version

class CompanyProfileTests(unittest.TestCase):
    def test_identity_policy_and_roles_are_not_client_configurable(self):
        current=load_profiles()[0]
        for malicious in ({'id':'gerico'},{'name':'Daltton'},{'role':'owner'},{'requireServiceIntent':False}):
            with self.assertRaises(ValueError):validate_configuration(malicious,current)

    def test_regional_and_amount_constraints_reject_invalid_boundaries(self):
        current=load_profiles()[0]
        for invalid in ({'states':['BR']},{'minValue':True},{'maxValue':float('inf')},{'minValue':200,'maxValue':100},{'terms':['']},{'synonyms':{'scope':'not-a-list'}}):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):validate_configuration(invalid,current)
        valid=validate_configuration({'states':['MG'],'minValue':0,'maxValue':250000,'synonyms':{'apoio':['suporte a rotinas']}},current)
        self.assertEqual(valid['name'],'Public');self.assertTrue(valid['requireServiceIntent'])
        self.assertNotEqual(classification_version([valid,load_profiles()[1]]),classification_version())

    def test_non_managers_cannot_write_or_lock_profile(self):
        db=MagicMock()
        with patch('radar.company_profiles.can_manage_company',return_value=False),self.assertRaises(AccessDenied):save_profile(db,'public','viewer@example.com',{'version':0,'configuration':{}})
        db.execute.assert_not_called()

    def test_stale_editor_does_not_overwrite_another_update(self):
        db=MagicMock()
        with patch('radar.company_profiles.can_manage_company',return_value=True),patch('radar.company_profiles.get_profile',return_value={'version':2}),self.assertRaises(ProfileConflict):save_profile(db,'public','manager@example.com',{'version':1,'configuration':{'enabled':False}})
        self.assertFalse(any('insert' in call.args[0] for call in db.execute.call_args_list))

    def test_request_profile_context_is_reset_after_failures(self):
        defaults=load_profiles();changed=deepcopy(defaults);changed[0]['enabled']=False
        with patch('radar.profiles.load_profiles',return_value=changed):
            with self.assertRaises(RuntimeError):
                with profile_context(MagicMock()):
                    self.assertEqual(classify('Contratação de palestrante para palestra gerencial')['scores']['Public'],0)
                    raise RuntimeError('request failed')
        self.assertTrue(load_profiles()[0]['enabled'])
