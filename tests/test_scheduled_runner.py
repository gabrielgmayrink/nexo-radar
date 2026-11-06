import importlib.util
import io
import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('radar_test_runner',Path(__file__).resolve().parents[1]/'scripts/run_scheduled_collection.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)


class ScheduledRunnerTests(unittest.TestCase):
    def test_runner_cannot_exceed_configured_free_usage_bound(self):
        for budget in (0,119,1441,True):
            with self.assertRaises(ValueError):runner.run('open',budget_seconds=budget)

    def test_final_batch_uses_remaining_time_and_resumes_same_execution(self):
        class Clock:
            now=0
            def read(self):return self.now
            def sleep(self,seconds):self.now+=seconds
        clock=Clock()
        class Opener:
            bodies=[]
            timeouts=[]
            def open(self,request,timeout):
                body=json.loads(request.data)
                self.bodies.append(body);self.timeouts.append(timeout)
                clock.now+=body['budgetSeconds']+5
                return io.BytesIO(json.dumps({'executionId':7,'done':False,'status':'running',
                    'requestErrors':0,'retryAfterSeconds':0}).encode())
        opener=Opener()
        with patch.object(runner,'identity',return_value='unit-test-only'),patch('builtins.print'):
            result=runner.run('incremental',opener=opener,clock=clock.read,sleeper=clock.sleep)
        self.assertEqual(result,0)
        self.assertEqual([b['budgetSeconds'] for b in opener.bodies],[140,140,100])
        self.assertEqual([b.get('executionId') for b in opener.bodies],[None,7,7])
        self.assertLess(clock.now,480)
        self.assertTrue(all(0<t<=235 for t in opener.timeouts))

    def test_identity_delay_cannot_start_a_batch_after_budget(self):
        class Clock:
            now=0
            def read(self):return self.now
        clock=Clock()
        class Opener:
            def open(self,*args,**kwargs):raise AssertionError('No batch time remains')
        def delayed_identity(opener):clock.now=400;return 'unit-test-only'
        with patch.object(runner,'identity',side_effect=delayed_identity),patch('builtins.print'):
            self.assertEqual(runner.run('open',opener=Opener(),clock=clock.read),0)

    def test_cooldown_does_not_hide_three_real_source_failures(self):
        class Clock:
            now=0
            def read(self):return self.now
            def sleep(self,seconds):self.now+=seconds
        class Opener:
            calls=0
            def open(self,*args,**kwargs):
                self.calls+=1
                return io.BytesIO(json.dumps({'executionId':1,'done':False,'status':'partial',
                    'requestErrors':self.calls,'retryAfterSeconds':1}).encode())
        clock=Clock();opener=Opener()
        with patch.object(runner,'identity',return_value='unit-test-only'),patch('builtins.print'):
            result=runner.run('open',opener=opener,clock=clock.read,sleeper=clock.sleep)
        self.assertEqual(result,1);self.assertEqual(opener.calls,3)

    def test_known_pncp_pause_is_reported_as_incomplete_with_saved_progress(self):
        scratch=Path(__file__).resolve().parents[1]/'work'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            summary=Path(directory)/'summary.md'
            with patch.dict('os.environ',{'GITHUB_STEP_SUMMARY':str(summary)}),patch('builtins.print') as output:
                result=runner.defer_source({'executionId':7,'error':'timeout'})
            self.assertEqual(result,0)
            self.assertIn('não concluiu a cobertura',summary.read_text(encoding='utf-8'))
            self.assertTrue(any('source_paused' in str(call) for call in output.call_args_list))

    def test_unknown_failure_or_missing_checkpoint_is_not_hidden(self):
        with patch('builtins.print') as output:
            for value in ({'executionId':7,'error':'storage_guard'},{'error':'timeout'},{'executionId':True,'error':'timeout'}):
                self.assertEqual(runner.defer_source(value),1)
        output.assert_not_called()
