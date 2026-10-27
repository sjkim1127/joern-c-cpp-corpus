#!/usr/bin/env python3
"""Preprocess pinned zlib inputs under explicit experimental C standard modes."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
REV='51b7f2abdade71cd9bb0e7a373ef2610ec6f9daf'
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''): h.update(block)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkout',type=Path,required=True)
    p.add_argument('--compiler',type=Path,required=True)
    p.add_argument('--standard',choices=['c11','c17','c23'],action='append',required=True)
    args=p.parse_args(); checkout=args.checkout.resolve(); compiler=args.compiler.resolve()
    def git(*args): return subprocess.check_output(['git','-C',str(checkout),*args],text=True).strip()
    if git('rev-parse','HEAD')!=REV or git('status','--porcelain','--untracked-files=all'):
        p.error('checkout must be clean at the pinned zlib commit')
    compiler_version=subprocess.check_output([str(compiler),'--version'],text=True).splitlines()[0]
    target=subprocess.check_output([str(compiler),'-dumpmachine'],text=True).strip()
    entries=[e for e in json.loads((ROOT/'manifests/inputs.json').read_text())['entries'] if e['project']=='zlib']
    output=ROOT/'workspace/prepared'; output.mkdir(parents=True,exist_ok=True)
    rows=[]
    for standard in dict.fromkeys(args.standard):
        for entry in entries:
            source=checkout/entry['source_path']; dest=output/f"{entry['id']}-{standard}.i"
            row={'id':f"{entry['id']}-{standard}",'source_id':entry['id'],'source_revision':REV,'source_sha256':sha(source),'language':'c','standard':standard,'standard_origin':'explicit experimental mode; not original project build', 'compiler_path':str(compiler),'compiler_sha256':sha(compiler),'compiler_version':compiler_version,'target':target,'platform':platform.platform(),'flags':['-std='+standard,'-I',str(checkout)],'preprocess_flags':['-E','-P'],'syntax_flags':['-fsyntax-only'], 'prepared_source':str(dest)}
            if row['source_sha256']!=entry['sha256']:
                row.update(status='source_hash_mismatch'); rows.append(row); continue
            flags=row['flags']
            syntax=subprocess.run([str(compiler),*flags,'-fsyntax-only',str(source)],capture_output=True,text=True)
            row['syntax_returncode']=syntax.returncode; row['syntax_stderr']=syntax.stderr[-3000:]
            if syntax.returncode:
                row['status']='compiler_rejected'; rows.append(row); continue
            prep=subprocess.run([str(compiler),*flags,'-E','-P',str(source)],capture_output=True)
            if prep.returncode:
                row.update(status='preprocess_error',preprocess_stderr=prep.stderr.decode(errors='replace')[-3000:]); rows.append(row); continue
            dest.write_bytes(prep.stdout); row.update(status='prepared',prepared_sha256=sha(dest),prepared_size=len(prep.stdout)); rows.append(row)
    manifest=output/'manifest.json'; manifest.write_text(json.dumps({'schema_version':1,'cases':rows},indent=2)+'\n')
    for row in rows: print(row['id'],row['status'])
    print('manifest:',manifest)
    return 0 if all(r['status']=='prepared' for r in rows) else 1
if __name__=='__main__': sys.exit(main())
