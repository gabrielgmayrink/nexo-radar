import importlib.util
import io
import json
import unittest
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
