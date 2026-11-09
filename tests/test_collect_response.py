"""A worker must finish reading each response without waiting for socket EOF."""
import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from api.collect import handler


class CollectResponseTests(unittest.TestCase):
    def test_responses_are_framed_on_a_reused_http_connection(self):
        class PersistentHandler(handler):
            protocol_version='HTTP/1.1'
            def log_message(self,*args):
                pass
        server=ThreadingHTTPServer(('127.0.0.1',0),PersistentHandler)
        server.daemon_threads=True
        thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':0.01},daemon=True)
        thread.start()
        connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=1)
        try:
            for _ in range(2):
                connection.request('GET','/api/collect')
                response=connection.getresponse()
                self.assertEqual(response.status,405)
                self.assertEqual(json.loads(response.read()),{'error':'Use POST.'})
        finally:
            connection.close();server.shutdown();server.server_close();thread.join(timeout=1)
