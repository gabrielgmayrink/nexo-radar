import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('bootstrap_guard',Path(__file__).resolve().parents[1]/'scripts/bootstrap_database.py')
module=importlib.util.module_from_spec(spec)
# The script's safe env reader is available in its own directory when executed normally.
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
spec.loader.exec_module(module)

class BootstrapSafetyTests(unittest.TestCase):
    def test_production_is_rejected_without_explicit_gate(self):
        with patch.dict(os.environ,{'SUPABASE_URL':'https://'+module.PRODUCTION_PROJECT+'.supabase.co'}):
            with self.assertRaisesRegex(ValueError,'Production requires'):module.validate_target(module.PRODUCTION_PROJECT)
    def test_mismatched_staging_url_is_rejected(self):
        with patch.dict(os.environ,{'SUPABASE_URL':'https://another-project.supabase.co'}):
            with self.assertRaisesRegex(ValueError,'Unexpected database'):module.validate_target('abcdefghijklmnopqrst')
