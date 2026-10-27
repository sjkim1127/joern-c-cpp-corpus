#!/usr/bin/env python3
"""Summarize prepared input and backend capture evidence without quality claims."""
import argparse
import hashlib
import json
from pathlib import Path

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--results-dir',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args(); prepared=json.loads(args.manifest.read_text()); native=json.loads((args.results_dir/'native-results.json').read_text())
    by_id={r['id']:r for r in native['results']}; rows=[]
    for case in prepared['cases']:
        n=by_id[case['id']]; row={k:case.get(k) for k in ('id','source_revision','source_sha256','language','standard','standard_origin','compiler_sha256','compiler_version','compilation_database_sha256','generated_header_sha256','target','prepared_sha256','prepared_size','status')}
        row.update(native_status=n['status'],native_function_count=n.get('function_count'),native_backend_sha256=n['backend_sha256'])
        ref=args.results_dir/'references'/f"{case['id']}.json"
        if ref.is_file():
            original=json.loads(ref.read_text())
            if original['prepared_sha256']!=case['prepared_sha256']: raise ValueError('reference input hash mismatch')
            row.update(original_status='captured',original_generator=original['generator'],original_function_count=len(original['functions']),original_reference_sha256=sha(ref))
        else: row['original_status']='not_captured'
        rows.append(row)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps({'schema_version':1,'interpretation':'output counts are diagnostic and include headers; not CFG correctness or project function counts','cases':rows},indent=2)+'\n')
if __name__=='__main__':main()
