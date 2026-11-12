import unittest
from unittest.mock import Mock,patch
from radar.notifications import send_delivery_test


class DeliveryTestTests(unittest.TestCase):
    def test_test_uses_only_server_allowlisted_recipient_and_is_deduplicated(self):
        sender=Mock();db=Mock()
        env={'RADAR_DELIVERY_TEST_EMAIL':'owner@example.com','RADAR_TEAM_EMAILS':'owner@example.com,company@example.com'}
        with patch.dict('os.environ',env,clear=True),patch('radar.notifications.reserve',return_value='fixture-id') as reserve:
            self.assertEqual(send_delivery_test(db,sender=sender)['sent'],1)
            self.assertEqual(sender.call_args.args[2],'owner@example.com')
            self.assertEqual(reserve.call_args.args[2],'test')
        sender.reset_mock()
        with patch.dict('os.environ',env,clear=True),patch('radar.notifications.reserve',return_value=None):
            self.assertEqual(send_delivery_test(db,sender=sender)['sent'],0);sender.assert_not_called()
        with patch.dict('os.environ',{**env,'RADAR_DELIVERY_TEST_EMAIL':'outside@example.com'},clear=True):
            with self.assertRaises(ValueError):send_delivery_test(db,sender=sender)
