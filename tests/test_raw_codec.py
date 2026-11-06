import gzip
import hashlib
import json
import unittest
from radar.raw_codec import encode_raw,decode_raw


class RawArchiveTests(unittest.TestCase):
    def test_lossless_unicode_numbers_nulls_and_original_hash(self):
        row={'objeto':'Licença de pesquisa de preços','valor':123.45,'itens':[None,0,False],'nested':{'b':2,'a':1}}
        digest=hashlib.sha256(json.dumps(row,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        compressed=encode_raw(row)
        self.assertEqual(decode_raw(None,compressed,digest),row)
        self.assertEqual(decode_raw(row,None,digest),row)
        self.assertEqual(encode_raw(row),compressed)

    def test_corruption_wrong_hash_and_multiple_representations_rejected(self):
        for payload,compressed,digest in [(None,b'corrupt','x'),(None,encode_raw({'a':1}),'x'),({},encode_raw({}),'x'),(None,None,'x')]:
            with self.assertRaises((ValueError,OSError)):decode_raw(payload,compressed,digest)

    def test_archive_expansion_is_bounded(self):
        compressed=gzip.compress(b' ' * 2_000_100)
        with self.assertRaises(ValueError):decode_raw(None,compressed,'x')
