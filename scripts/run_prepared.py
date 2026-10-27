#!/usr/bin/env python3
"""Run strict Rust-Joern and generate a manifest for original Joern capture."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--binary',type=Path,required=True)
    p.add_argument('--timeout',type=int,default=60)
    p.add_argument('--output-dir',type=Path,default=ROOT/'workspace/prepared-evaluation')
    args=p.parse_args(); binary=args.binary.resolve(); backend_hash=sha(binary)
    source=json.loads(args.manifest.read_text()); records=[]; cases=[]
    out=args.output_dir.resolve(); out.mkdir(parents=True,exist_ok=True)
    for row in source['cases']:
        record={'id':row['id'],'standard':row['standard'],'backend_sha256':backend_hash,'prepared_sha256':row.get('prepared_sha256')}
        if row['status']!='prepared': record['status']='preparation_unavailable'; records.append(record); continue
        path=Path(row['prepared_source'])
        if not path.is_file() or sha(path)!=row['prepared_sha256']:
            record['status']='input_hash_mismatch'; records.append(record); continue
        cases.append({'id':row['id'],'language':row['language'],'prepared_source':str(path.resolve()),'prepared_sha256':row['prepared_sha256'],'reference':str((out/'references'/f"{row['id']}.json").resolve())})
        graph=out/f"{row['id']}.json"; graph.unlink(missing_ok=True)
        cmd=[str(binary),'analyze',str(path),'--language',row['language'],'--preprocessed','--strict','--output',str(graph)]
        try:
            proc=subprocess.run(cmd,capture_output=True,text=True,timeout=args.timeout)
            record.update(returncode=proc.returncode,stderr_tail=proc.stderr[-3000:])
            if proc.returncode: record['status']='backend_error'
            elif not graph.is_file(): record['status']='missing_output'
            else:
                parsed=json.loads(graph.read_text()); record.update(status='output' if parsed.get('functions') else 'no_functions',function_count=len(parsed.get('functions',[])),graph_sha256=sha(graph))
        except subprocess.TimeoutExpired: record['status']='timeout'
        except (OSError,ValueError) as e: record.update(status='runner_error',error=str(e))
        records.append(record); print(record['id'],record['status'],flush=True)
    (out/'native-results.json').write_text(json.dumps({'schema_version':1,'results':records},indent=2)+'\n')
    (out/'reference-manifest.json').write_text(json.dumps({'schema_version':1,'cases':cases},indent=2)+'\n')
if __name__=='__main__': main()
