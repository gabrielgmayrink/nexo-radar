from unittest.mock import patch
from profile_fixtures import TEST_PROFILES
import json
import tempfile
import unittest
from pathlib import Path
from radar.worker import run, connect

class Client:
    def get_page(self,*args,**kwargs):
        return {'data':[{'numeroControlePNCP':'1-1-1/2026','orgaoEntidade':{'cnpj':'1'},'anoCompra':2026,'sequencialCompra':1,'objetoCompra':'Licença de plataforma de pesquisa de preços','situacaoCompraId':1,'tipoInstrumentoConvocatorioCodigo':1}], 'totalPaginas':1}

@patch('radar.profiles.load_profiles', lambda: TEST_PROFILES)
class WorkerTests(unittest.TestCase):
    def test_invalid_page_is_rolled_back(self):
        class InvalidClient(Client):
            def get_page(self,*args,**kwargs):
                page=super().get_page(*args,**kwargs)
                page['data'].append({'objetoCompra':'Registro sem identificador'})
                return page
        Path('work').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=Path('work').resolve()) as folder:
            db=Path(folder)/'state.sqlite'; output=Path(folder)/'catalog.json'
            result=run(db,output,client=InvalidClient())
            self.assertTrue(result['failures'])
            connection=connect(db)
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM opportunity').fetchone()[0],0)
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM raw').fetchone()[0],0)
            connection.close()
    def test_total_failure_preserves_previous_catalog(self):
        class FailingClient:
            def get_page(self,*args,**kwargs):raise RuntimeError('offline')
        Path('work').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=Path('work').resolve()) as folder:
            db=Path(folder)/'state.sqlite'; output=Path(folder)/'catalog.json'
            output.write_text('{"previous":true}')
            result=run(db,output,client=FailingClient())
            self.assertTrue(result['failures'])
            self.assertEqual(output.read_text(),'{"previous":true}')
    def test_repeated_collection_is_idempotent(self):
        Path('work').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=Path('work').resolve()) as folder:
            db=Path(folder)/'state.sqlite'; output=Path(folder)/'catalog.json'
            for _ in range(2):
                result=run(db,output,client=Client())
                self.assertEqual(result['failures'],[])
            conn=connect(db)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM raw').fetchone()[0],1)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM opportunity').fetchone()[0],1)
            conn.close()
            self.assertEqual(len(json.loads(output.read_text(encoding='utf-8'))['opportunities']),1)

if __name__=='__main__':unittest.main()
