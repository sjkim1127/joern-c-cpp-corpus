#!/usr/bin/env python3
"""Use an explicit CMake compilation database for pinned Snappy sources."""
import argparse, hashlib, json, os, shlex, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REV='2a6c78c781cb76ad191795449cb2267f33138150'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('checkout','database','output-dir'): p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args(); root=a.checkout.resolve(); db=a.database.resolve(); output=a.output_dir.resolve(); output.mkdir(parents=True,exist_ok=True)
    git=lambda *args:subprocess.check_output(['git','-C',str(root),*args],text=True).strip()
    if git('rev-parse','HEAD')!=REV or git('status','--porcelain','--untracked-files=all'): p.error('checkout must be clean and pinned')
    entries=[e for e in json.loads((ROOT/'manifests/inputs.json').read_text())['entries'] if e['id'].startswith('snappy-raw-')]
    commands=json.loads(db.read_text()); rows=[]
    for entry in entries:
        source=(root/entry['source_path']).resolve(); matches=[c for c in commands if (Path(c['directory'])/c['file']).resolve()==source]
        if len(matches)!=1: p.error('source must have exactly one compilation command: '+str(source))
        c=matches[0]; args=c.get('arguments') or shlex.split(c['command']); cwd=Path(c['directory']).resolve(); compiler=Path(args[0]).absolute()
        if any(x in ('&&',';','|') or x.startswith('@') for x in args): p.error('unsupported compilation command')
        flags=[]; i=1
        while i<len(args):
            arg=args[i]
            if arg=='-o': i+=2; continue
            if arg=='-c' or (cwd/arg).resolve()==source: i+=1; continue
            flags.append(arg); i+=1
        std=[x for x in flags if x.startswith('-std=')]
        if len(std)!=1: p.error('one explicit -std option required')
        mode=std[0].split('=',1)[1]; dest=output/(entry['id']+'-'+mode+'.ii')
        row={'id':entry['id']+'-'+mode,'source_id':entry['id'],'source_revision':REV,'source_sha256':sha(source),'language':'cpp','standard':mode,'standard_origin':'explicit local CMake configuration; not original corpus build','compiler_path':str(compiler),'compiler_sha256':sha(compiler),'compiler_version':subprocess.check_output([str(compiler),'--version'],text=True).splitlines()[0],'target':subprocess.check_output([str(compiler),'-dumpmachine'],text=True).strip(),'compilation_database_sha256':sha(db),'generated_header_sha256':{name:sha(db.parent/name) for name in ('config.h','snappy-stubs-public.h') if (db.parent/name).is_file()},'flags':flags,'working_directory':str(cwd),'preprocess_flags':['-E'],'prepared_source':str(dest)}
        if row['source_sha256']!=entry['sha256']: row['status']='source_hash_mismatch';rows.append(row);continue
        check=subprocess.run([str(compiler),*flags,'-fsyntax-only',str(source)],cwd=cwd,capture_output=True,text=True);row['syntax_returncode']=check.returncode;row['syntax_stderr']=check.stderr[-3000:]
        if check.returncode: row['status']='compiler_rejected';rows.append(row);continue
        prep=subprocess.run([str(compiler),*flags,'-E',str(source)],cwd=cwd,capture_output=True)
        if prep.returncode: row.update(status='preprocess_error',preprocess_stderr=prep.stderr.decode(errors='replace')[-3000:]);rows.append(row);continue
        dest.write_bytes(prep.stdout);row.update(status='prepared',prepared_sha256=sha(dest),prepared_size=len(prep.stdout));rows.append(row)
    (output/'manifest.json').write_text(json.dumps({'schema_version':1,'cases':rows},indent=2)+'\n')
    for row in rows: print(row['id'],row['status'])
    return int(any(r['status']!='prepared' for r in rows))
if __name__=='__main__':raise SystemExit(main())
