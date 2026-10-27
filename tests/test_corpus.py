import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
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
    def test_prepared_hash_mismatch_never_invokes_backend(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp); source=tmp/'input.i'; source.write_text('changed')
            binary=tmp/'backend'; binary.write_text('not an executable')
            manifest=tmp/'manifest.json'; manifest.write_text(json.dumps({'cases':[{
                'id':'one','standard':'c11','status':'prepared','language':'c',
                'prepared_source':str(source),'prepared_sha256':'0'*64}]}))
            out=tmp/'results'
            subprocess.run([sys.executable,str(ROOT/'scripts'/'run_prepared.py'),
                '--manifest',str(manifest),'--binary',str(binary),'--output-dir',str(out)],check=True,capture_output=True)
            result=json.loads((out/'native-results.json').read_text())['results'][0]
            self.assertEqual(result['status'],'input_hash_mismatch')
            self.assertFalse(json.loads((out/'reference-manifest.json').read_text())['cases'])

    def test_both_hash_contracts_fail_closed(self):
        data=b'abc'
        git=hashlib.sha1(b'blob 3\0'+data).hexdigest()
        for entry in ({'size_bytes':3,'git_blob_sha1':git}, {'size_bytes':3,'sha256':hashlib.sha256(data).hexdigest()}):
            self.assertTrue(corpus.valid(data,entry))
            self.assertFalse(corpus.valid(b'abd',entry))
            self.assertFalse(corpus.valid(b'ab',entry))
if __name__=='__main__': unittest.main()
