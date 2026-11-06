import unittest
import json
from unittest.mock import patch
from api.index import handler
from api.detail import handler as DetailHandler

class APITests(unittest.TestCase):
    def invoke(self, cls, path):
        instance=object.__new__(cls)
        instance.path=path
        result=[]
        instance.respond=lambda status,payload:result.append((status,payload))
        instance.do_GET()
        return result[0]

    def test_catalog_pagination(self):
        fixture={'metrics':{},'opportunities':[{'id':str(i),'object':'Fixture','organization':'Test','city':'Test','suggestedOffer':'Daltton'} for i in range(5)]}
        with patch('pathlib.Path.read_text',return_value=json.dumps(fixture)):
            status,payload=self.invoke(handler,'/api/opportunities?limit=2')
        self.assertEqual(status,200)
        self.assertEqual(len(payload['opportunities']),2)
        self.assertGreater(payload['total'],2)

    def test_initial_catalog_is_empty_and_explicitly_pending(self):
        status,payload=self.invoke(handler,'/api/opportunities')
        self.assertEqual(status,200)
        self.assertEqual(payload['opportunities'],[])
        self.assertTrue(payload['setupPending'])

    def test_invalid_page(self):
        self.assertEqual(self.invoke(handler,'/api/opportunities?page=abc')[0],400)

    def test_detail_rejects_arbitrary_destination(self):
        self.assertEqual(self.invoke(DetailHandler,'/api/detail?id=https://example.com')[0],400)

if __name__=='__main__':unittest.main()
