import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from verify_staging_backup import validate_source


class ProductionBackupBoundaryTests(unittest.TestCase):
    def test_default_runner_refuses_production_and_explicit_runner_refuses_admin(self):
        ref='hxngkmrsthyjycxaellk'
        backup='postgresql://nexo_backup_login.'+ref+':fixture@pooler.example/postgres'
        with self.assertRaises(ValueError):validate_source(ref,backup)
        with self.assertRaises(ValueError):validate_source(ref,backup.replace('nexo_backup_login','postgres'),production=True)
        validate_source(ref,backup,production=True)
        with self.assertRaises(ValueError):validate_source('odntvxflshrwxhdqtepm',backup,production=True)
