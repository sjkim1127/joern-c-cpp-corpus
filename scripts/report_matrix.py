#!/usr/bin/env python3
"""Summarize the recorded six-platform Zlib smoke, verifying artifact hashes."""
import collections, hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    expected={'macos-arm64':('Mach-O','aarch64'),'macos-x64':('Mach-O','x86_64'),'linux-arm64':('ELF','aarch64'),'linux-x64':('ELF','x86_64'),'windows-x86':('COFF','x86'),'windows-x64':('COFF','x86_64')}
    rows=[]
    for profile,(fmt,arch) in expected.items():
        prepared=ROOT/'workspace'/('matrix-'+profile); evaluation=ROOT/'workspace'/('matrix-'+profile+'-eval')
        case=json.loads((prepared/'manifest.json').read_text())['cases'][0]
        native=json.loads((evaluation/'native-results.json').read_text())['results'][0]
        comparison=json.loads((evaluation/'comparison.json').read_text())
        input_path=prepared/'zlib-compress.c-c11.i'; obj=prepared/'zlib-compress.c-c11.o'
        ref=evaluation/'references'/'zlib-compress.c-c11.json'; graph=evaluation/'zlib-compress.c-c11.json'
        if case['status']!='prepared' or case['object_identity']['format']!=fmt or case['object_identity']['architecture']!=arch: raise ValueError('unexpected object identity '+profile)
        if (sha(input_path)!=case['prepared_sha256'] or sha(obj)!=case['object_sha256'] or native['prepared_sha256']!=case['prepared_sha256'] or native['graph_sha256']!=sha(graph) or comparison['prepared_sha256']!=case['prepared_sha256'] or comparison['reference_sha256']!=sha(ref) or comparison['native_graph_sha256']!=sha(graph)):
            raise ValueError('artifact hash mismatch '+profile)
        rows.append({'profile':profile,'target_triple':case['target'],'compiler_version':case['compiler_version'],'compiler_sha256':case['compiler_sha256'],'standard':case['standard'],'source_sha256':case['source_sha256'],'prepared_sha256':case['prepared_sha256'],'object_sha256':case['object_sha256'],'object_identity':case['object_identity'],'backend_sha256':native['backend_sha256'],'native_graph_sha256':sha(graph),'reference_sha256':sha(ref),'native_status':native['status'],'cfg_status_counts':dict(collections.Counter(r['status'] for r in comparison['rows'])),'comparison_rows':comparison['rows']})
    dest=ROOT/'reports/platform-matrix-2026-10-27.json';dest.write_text(json.dumps({'schema_version':1,'scope':'one source TU, per-profile separate input, cross-compiled objects, not runtime validation','cases':rows},indent=2)+'\n')
    print(dest)
if __name__=='__main__':main()
