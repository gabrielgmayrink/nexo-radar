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
        fixture={'metrics':{},'opportunities':[{'id':str(i),'object':'Fixture','organization':'Test','city':'Test','suggestedOffer':'Public'} for i in range(5)]}
        with patch('pathlib.Path.read_text',return_value=json.dumps(fixture)):
            status,payload=self.invoke(handler,'/api/opportunities?limit=2')
        self.assertEqual(status,200)
        self.assertEqual(len(payload['opportunities']),2)
        self.assertGreater(payload['total'],2)

    def test_initial_catalog_is_empty_and_explicitly_pending(self):
        status,payload=self.invoke(handler,'/api/opportunities')
        self.assertEqual(status,200)
        self.assertEqual(payload['opportunities'],[])
        self.assertFalse(payload['setupPending'])

    def test_invalid_page(self):
        self.assertEqual(self.invoke(handler,'/api/opportunities?page=abc')[0],400)

    def test_detail_rejects_arbitrary_destination(self):
        self.assertEqual(self.invoke(DetailHandler,'/api/detail?id=https://example.com')[0],400)

    def test_bulk_catalog_is_returned_in_one_response(self):
        fixture={'metrics':{},'opportunities':[{'id':str(i),'object':'Desenvolvimento de sistemas','suggestedOffer':'Public'} for i in range(125)]}
        with patch('pathlib.Path.read_text',return_value=json.dumps(fixture)):
            status,payload=self.invoke(handler,'/api/opportunities?bulk=1')
        self.assertEqual(status,200)
        self.assertEqual(len(payload['opportunities']),125)
        self.assertEqual(payload['total'],125)

    def test_invalid_pagination_never_loads_the_database(self):
        with patch.dict('os.environ',{'RADAR_CATALOG_STORE':'supabase'}),patch('api.index.load_database_catalog') as load:
            self.assertEqual(self.invoke(handler,'/api/opportunities?page=invalid')[0],400)
        load.assert_not_called()

    def test_api_search_uses_the_same_phrase_and_exclusion_semantics(self):
        fixture={'opportunities':[{'id':'1','object':'Desenvolvimento de sistemas','city':'Belo Horizonte','suggestedOffer':'Public'},
                                  {'id':'2','object':'Equipamentos de informática','city':'Belo Horizonte','suggestedOffer':'Public'}]}
        from urllib.parse import urlencode
        with patch('pathlib.Path.read_text',return_value=json.dumps(fixture)):
            status,payload=self.invoke(handler,'/api/opportunities?'+urlencode({'q':'"desenvolvimento de sistemas" horizonte -equipamentos'}))
        self.assertEqual(status,200)
        self.assertEqual([row['id'] for row in payload['opportunities']],['1'])

if __name__=='__main__':unittest.main()
