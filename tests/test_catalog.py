import json
import tempfile
import unittest
from pathlib import Path
from radar.build_catalog import build

class CatalogTests(unittest.TestCase):
    def test_collection_date_comes_from_source_not_fixed_constant(self):
        Path('work').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=Path('work').resolve()) as folder:
            source=Path(folder)/'source.jsonl';output=Path(folder)/'catalog.json'
            source.write_text(json.dumps({'coletado_em':'2026-11-07T10:00:00-03:00','registro':{'numeroControlePNCP':'test','objetoCompra':'Licença de plataforma de pesquisa de preços'}}),encoding='utf-8')
            build(source,output)
            self.assertEqual(json.loads(output.read_text(encoding='utf-8'))['collectionDate'],'2026-11-07')
            build(source,output,collection_date='2026-11-08')
            self.assertEqual(json.loads(output.read_text(encoding='utf-8'))['collectionDate'],'2026-11-08')
