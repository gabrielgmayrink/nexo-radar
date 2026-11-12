import unittest
from unittest.mock import patch,MagicMock
from api.index import handler
from radar.company_access import AccessDenied

class APITests(unittest.TestCase):
    def invoke(self,path):
        instance=object.__new__(handler);instance.path=path;instance.headers={}
        result=[];instance.respond=lambda status,payload:result.append((status,payload));instance.do_GET()
        return result[0]

    def test_pagination_is_delegated_to_authorized_server_query(self):
        fixture={'metrics':{},'opportunities':[{'id':'1'}],'total':2401,'page':101,'pages':201}
        with patch('api.index.session_token',return_value='token'),patch('api.index.PostgresStore') as store,patch('api.index.resolve_access',return_value=('member@example.com','public',['public'])),patch('api.index.load_catalog_page',return_value=fixture) as load:
            status,payload=self.invoke('/api/opportunities?company=public&page=101&limit=12&uf=MG&q=treinamento')
            self.assertEqual((status,payload),(200,fixture))
            self.assertEqual(load.call_args.args[1],'public')
            self.assertEqual(load.call_args.args[2]['page'],['101'])
            self.assertIs(load.call_args.args[3],store.return_value.db)
            store.return_value.close.assert_called_once()

    def test_invalid_filters_do_not_connect_to_database(self):
        for query in ('page=abc','page=0','limit=101','uf=INVALID','minValue=-2','publishedFrom=2026-02-31','bulk=1','sort=unsafe'):
            with self.subTest(query=query),patch('api.index.PostgresStore') as store:
                self.assertEqual(self.invoke('/api/opportunities?'+query)[0],400);store.assert_not_called()

    def test_anonymous_requests_do_not_connect(self):
        with patch('api.index.PostgresStore') as store:
            self.assertEqual(self.invoke('/api/opportunities')[0],401);store.assert_not_called()

    def test_membership_failure_never_loads_catalog(self):
        with patch('api.index.session_token',return_value='token'),patch('api.index.PostgresStore'),patch('api.index.resolve_access',side_effect=AccessDenied()),patch('api.index.load_catalog_page') as load:
            self.assertEqual(self.invoke('/api/opportunities?company=gerico')[0],403);load.assert_not_called()

    def test_storage_error_is_redacted_and_connection_closed(self):
        with patch('api.index.session_token',return_value='token'),patch('api.index.PostgresStore') as store,patch('api.index.resolve_access',side_effect=RuntimeError('secret connection value')):
            status,body=self.invoke('/api/opportunities')
            self.assertEqual(status,503);self.assertNotIn('secret',str(body));store.return_value.close.assert_called_once()
