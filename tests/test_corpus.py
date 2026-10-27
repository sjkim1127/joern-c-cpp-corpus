import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('corpus',ROOT/'scripts'/'corpus.py')
corpus=importlib.util.module_from_spec(spec); spec.loader.exec_module(corpus)

class CorpusTest(unittest.TestCase):
    def test_manifest_contract(self):
        entries=json.loads((ROOT/'manifests'/'inputs.json').read_text())['entries']
        self.assertEqual(len(entries),len({x['id'] for x in entries}))
        self.assertEqual({x['language'] for x in entries},{'c','cpp'})
        self.assertTrue(all(x['source_path'] and x['standard']=='unknown' for x in entries))
        self.assertTrue(all(x['url'].startswith('https://') and x['size_bytes'] > 0 for x in entries))
    def test_both_hash_contracts_fail_closed(self):
        data=b'abc'
        git=hashlib.sha1(b'blob 3\0'+data).hexdigest()
        for entry in ({'size_bytes':3,'git_blob_sha1':git}, {'size_bytes':3,'sha256':hashlib.sha256(data).hexdigest()}):
            self.assertTrue(corpus.valid(data,entry))
            self.assertFalse(corpus.valid(b'abd',entry))
            self.assertFalse(corpus.valid(b'ab',entry))
if __name__=='__main__': unittest.main()
