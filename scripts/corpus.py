#!/usr/bin/env python3
"""Fetch pinned inputs or run Rust-Joern with resumable per-input records."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'manifests' / 'inputs.json'
WORK = ROOT / 'workspace'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def fetch(entry):
    suffix = '.ii' if entry['input_kind'] == 'preprocessed_tu' else '.c'
    path = WORK / 'inputs' / (entry['id'] + suffix)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and valid(path.read_bytes(), entry):
        return path
    with urllib.request.urlopen(entry['url'], timeout=90) as response:
        data = response.read()
    if not valid(data, entry):
        raise ValueError('input checksum or size mismatch')
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as out:
        out.write(data)
        temp = out.name
    os.replace(temp, path)
    return path

def valid(data, entry):
    if len(data) != entry['size_bytes']:
        return False
    if 'sha256' in entry:
        return hashlib.sha256(data).hexdigest() == entry['sha256']
    header = b'blob ' + str(len(data)).encode() + b'\0'
    return hashlib.sha1(header + data).hexdigest() == entry['git_blob_sha1']

def atomic_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as out:
        json.dump(payload, out, indent=2)
        out.write('\n')
        temp = out.name
    os.replace(temp, path)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=['fetch','run'])
    p.add_argument('--project',action='append')
    p.add_argument('--limit',type=int)
    p.add_argument('--binary',type=Path)
    p.add_argument('--timeout',type=int,default=60)
    p.add_argument('--no-resume',action='store_true')
    args=p.parse_args()
    entries=json.loads(MANIFEST.read_text())['entries']
    if args.project: entries=[e for e in entries if e['project'] in args.project]
    if args.limit is not None: entries=entries[:args.limit]
    if args.action=='run' and (not args.binary or not args.binary.is_file()): p.error('run requires --binary')
    binary=args.binary.resolve() if args.binary else None
    binary_hash=digest(binary) if binary else None
    for e in entries:
        result=WORK/'results'/f"{e['id']}.json"
        record={'id':e['id'],'project':e['project'],'language':e['language'],'standard':e['standard'],'input_kind':e['input_kind'],'backend_sha256':binary_hash,'timeout_seconds':args.timeout,'entry_sha256':hashlib.sha256(json.dumps(e,sort_keys=True).encode()).hexdigest()}
        if result.exists() and not args.no_resume and binary:
            old=json.loads(result.read_text())
            if all(old.get(k)==record.get(k) for k in ('id','backend_sha256','timeout_seconds','input_kind','entry_sha256')) and old.get('status')!='fetch_error' and (old.get('status') != 'output' or ((WORK/'graphs'/f"{e['id']}.json").is_file() and digest(WORK/'graphs'/f"{e['id']}.json") == old.get('graph_sha256'))):
                print(e['id'],old['status'],'(cached)',flush=True); continue
        try:
            path=fetch(e); record['input_sha256']=digest(path)
        except Exception as exc:
            record.update(status='fetch_error',error=str(exc)); atomic_json(result,record); print(e['id'],'fetch_error',flush=True); continue
        if args.action=='fetch': print(e['id'],'fetched',flush=True); continue
        graph=WORK/'graphs'/f"{e['id']}.json"; graph.parent.mkdir(parents=True,exist_ok=True)
        if graph.exists(): graph.unlink()
        command=[str(binary),'analyze',str(path),'--language',e['language'],'--strict','--output',str(graph)]
        if e['input_kind']=='preprocessed_tu': command.append('--preprocessed')
        try:
            proc=subprocess.run(command,capture_output=True,text=True,timeout=args.timeout)
            record['returncode']=proc.returncode
            record['stderr_tail']=proc.stderr[-4000:]
            if proc.returncode: record['status']='backend_error'
            elif not graph.exists(): record['status']='missing_output'
            else:
                output=json.loads(graph.read_text())
                record['function_count']=len(output.get('functions',[]))
                record['diagnostics_count']=len(output.get('diagnostics',[]))
                record['status']='output' if record['function_count'] else 'no_functions'
                record['graph_sha256']=digest(graph)
        except subprocess.TimeoutExpired:
            record['status']='timeout'
        except (OSError,ValueError) as exc:
            record.update(status='runner_error',error=str(exc))
        atomic_json(result,record); print(e['id'],record['status'],flush=True)
if __name__=='__main__': main()
