import unittest
from unittest.mock import patch
from radar.postgres_store import connection_string


class ServiceCredentialTests(unittest.TestCase):
    def test_enforced_services_never_fall_back_to_management_credentials(self):
        env={'RADAR_DB_SERVICE_CREDENTIALS':'1','SUPABASE_URL':'https://abcdefghijklmnopqrst.supabase.co',
             'POSTGRES_URL_NON_POOLING':'postgresql://postgres.abcdefghijklmnopqrst:fixture@localhost/postgres'}
        with patch.dict('os.environ',env,clear=True),patch('radar.postgres_store.PROJECT_REF','abcdefghijklmnopqrst'):
            for service in ('api','collector'):
                with self.assertRaisesRegex(ValueError,'Dedicated service credential required'):connection_string(service=service)
            with self.assertRaisesRegex(ValueError,'Invalid database service'):connection_string(service='arbitrary-role')
