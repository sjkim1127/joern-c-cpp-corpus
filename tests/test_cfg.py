import importlib.util
from pathlib import Path
import unittest
import json
import subprocess
import sys
import tempfile
try:
    import networkx
except ImportError:
    networkx=None
ROOT=Path(__file__).resolve().parents[1]
@unittest.skipIf(networkx is None,'networkx is required for topology comparisons')
class CfgTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location('compare_cfg',ROOT/'scripts/compare_cfg.py')
        cls.cfg=importlib.util.module_from_spec(spec); spec.loader.exec_module(cls.cfg)
    def test_source_markers_exclude_header_functions(self):
        text='# 1 "/src/main.c"\nint f(void) {\nreturn 1;\n}\n# 1 "/src/header.h"\nint g(void){}\n'
        mapping=self.cfg.source_lines(text)
        self.assertEqual(self.cfg.identity({'name':'f','start_line':2,'end_line':4},mapping,Path('/src/main.c')),('f',1,3))
        self.assertIsNone(self.cfg.identity({'name':'g','start_line':6,'end_line':6},mapping,Path('/src/main.c')))
        self.assertIsNone(self.cfg.identity({'name':'f','start_line':3,'end_line':6},mapping,Path('/src/main.c')))
    def test_native_graph_hash_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp); prepared=d/'input.i'; prepared.write_text('int f(void){}')
            source=d/'source.c'; source.write_text('int f(void){}')
            import hashlib
            h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
            native=d/'native.json';native.write_text('{}')
            reference=d/'reference.json';reference.write_text(json.dumps({'prepared_sha256':h(prepared)}))
            manifest=d/'manifest.json';manifest.write_text(json.dumps({'cases':[{'id':'x','prepared_sha256':h(prepared),'source_sha256':h(source)}]}))
            results=d/'results.json';results.write_text(json.dumps({'results':[{'id':'x','prepared_sha256':h(prepared),'status':'output','graph_sha256':'0'*64}]}))
            result=subprocess.run([sys.executable,str(ROOT/'scripts/compare_cfg.py'),'--case-id','x',
                '--prepared',str(prepared),'--source',str(source),'--native',str(native),
                '--reference',str(reference),'--manifest',str(manifest),'--native-results',str(results),
                '--output',str(d/'out.json')],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('hash mismatch',result.stderr)

    def test_topology_and_boundary_are_not_node_counts(self):
        left={'nodes':[0,1,2,3],'edges':[[0,1],[0,2],[1,3],[2,3]],'entry':[0],'exit':[3]}
        right={'nodes':[0,1,2,3],'edges':[[0,1],[1,2],[2,3],[0,3]],'entry':[0],'exit':[3]}
        l,err=self.cfg.graph_from_cfg(left,True); self.assertIsNone(err)
        r,err=self.cfg.graph_from_cfg(right,True); self.assertIsNone(err)
        self.assertEqual(self.cfg.compare_graphs(l,l,2),'isomorphic')
        self.assertEqual(self.cfg.compare_graphs(l,r,2),'different')
        right['exit']=[]; self.assertEqual(self.cfg.graph_from_cfg(right,True)[1],'missing_entry_or_exit')
        left['edges'].append([0,1]);self.assertEqual(self.cfg.graph_from_cfg(left,True)[1],'parallel_edges_unsupported')
