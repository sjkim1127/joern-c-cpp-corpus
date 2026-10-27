#!/usr/bin/env python3
"""Use an explicit CMake compilation database for pinned Snappy sources."""
import argparse, hashlib, json, os, shlex, subprocess
from pathlib import Path
from prepare_zlib import object_identity
ROOT=Path(__file__).resolve().parents[1]
REV='2a6c78c781cb76ad191795449cb2267f33138150'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def expand_response_files(args,cwd,depth=0):
    if depth>4: raise ValueError('response nesting exceeds limit')
    cwd=cwd.resolve()
    out=[]; hashes={}
    for arg in args:
        if not arg.startswith('@'): out.append(arg); continue
        path=(cwd/arg[1:]).resolve()
        if not path.is_relative_to(cwd.resolve()) or not path.is_file(): raise ValueError('response path outside build directory or missing')
        data=path.read_bytes()
        if len(data)>1024*1024: raise ValueError('response file exceeds size limit')
        nested,nested_hashes=expand_response_files(shlex.split(data.decode()),cwd,depth+1)
        hashes[str(path.relative_to(cwd))]=hashlib.sha256(data).hexdigest(); hashes.update(nested_hashes); out.extend(nested)
    return out,hashes

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('checkout','database','output-dir'): p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--verify-object',action='store_true')
    p.add_argument('--expected-format',choices=['ELF','COFF','Mach-O'])
    p.add_argument('--expected-arch',choices=['x86','x86_64','aarch64'])
    a=p.parse_args()
    if a.verify_object and not (a.expected_format and a.expected_arch): p.error('--verify-object requires expected format and architecture')
    root=a.checkout.resolve(); db=a.database.resolve(); output=a.output_dir.resolve(); output.mkdir(parents=True,exist_ok=True)
    git=lambda *args:subprocess.check_output(['git','-C',str(root),*args],text=True).strip()
    if git('rev-parse','HEAD')!=REV or git('status','--porcelain','--untracked-files=all'): p.error('checkout must be clean and pinned')
    entries=[e for e in json.loads((ROOT/'manifests/inputs.json').read_text())['entries'] if e['id'].startswith('snappy-raw-')]
    commands=json.loads(db.read_text()); rows=[]
    for entry in entries:
        source=(root/entry['source_path']).resolve(); matches=[c for c in commands if (Path(c['directory'])/c['file']).resolve()==source]
        if len(matches)!=1: p.error('source must have exactly one compilation command: '+str(source))
        c=matches[0]; args=c.get('arguments') or shlex.split(c['command']); cwd=Path(c['directory']).resolve(); compiler=Path(args[0]).absolute()
        try: args,response_hashes=expand_response_files(args,cwd)
        except (ValueError,UnicodeError) as e: p.error(str(e))
        if any(x in ('&&',';','|') for x in args): p.error('unsupported compilation command')
        flags=[]; i=1
        while i<len(args):
            arg=args[i]
            if arg=='-o': i+=2; continue
            if arg=='-c' or (cwd/arg).resolve()==source: i+=1; continue
            flags.append(arg); i+=1
        std=[x for x in flags if x.startswith('-std=')]
        if len(std)!=1: p.error('one explicit -std option required')
        mode=std[0].split('=',1)[1]; dest=output/(entry['id']+'-'+mode+'.ii')
        row={'id':entry['id']+'-'+mode,'source_id':entry['id'],'source_revision':REV,'source_sha256':sha(source),'language':'cpp','standard':mode,'standard_origin':'explicit local CMake configuration; not original corpus build','compiler_path':str(compiler),'compiler_sha256':sha(compiler),'compiler_version':subprocess.check_output([str(compiler),'--version'],text=True).splitlines()[0],'target':subprocess.check_output([str(compiler),'-dumpmachine'],text=True).strip(),'compilation_database_sha256':sha(db),'response_file_sha256':response_hashes,'generated_header_sha256':{name:sha(db.parent/name) for name in ('config.h','snappy-stubs-public.h') if (db.parent/name).is_file()},'flags':flags,'working_directory':str(cwd),'preprocess_flags':['-E'],'prepared_source':str(dest)}
        if row['source_sha256']!=entry['sha256']: row['status']='source_hash_mismatch';rows.append(row);continue
        check=subprocess.run([str(compiler),*flags,'-fsyntax-only',str(source)],cwd=cwd,capture_output=True,text=True);row['syntax_returncode']=check.returncode;row['syntax_stderr']=check.stderr[-3000:]
        if check.returncode: row['status']='compiler_rejected';rows.append(row);continue
        prep=subprocess.run([str(compiler),*flags,'-E',str(source)],cwd=cwd,capture_output=True)
        if prep.returncode: row.update(status='preprocess_error',preprocess_stderr=prep.stderr.decode(errors='replace')[-3000:]);rows.append(row);continue
        dest.write_bytes(prep.stdout);row.update(status='prepared',prepared_sha256=sha(dest),prepared_size=len(prep.stdout))
        if a.verify_object:
            obj=output/(entry['id']+'-'+mode+'.o')
            built=subprocess.run([str(compiler),*flags,'-c',str(source),'-o',str(obj)],cwd=cwd,capture_output=True,text=True)
            row['object_returncode']=built.returncode; row['object_expected']={'format':a.expected_format,'architecture':a.expected_arch}
            if built.returncode: row.update(status='object_compile_error',object_stderr=built.stderr[-3000:])
            else:
                row['object_sha256']=sha(obj); row['object_identity']=object_identity(obj)
                actual=row['object_identity']
                if actual is None: row['status']='object_format_unrecognized'
                elif actual['format']!=a.expected_format or actual['architecture']!=a.expected_arch: row['status']='object_target_mismatch'
        rows.append(row)
    (output/'manifest.json').write_text(json.dumps({'schema_version':1,'cases':rows},indent=2)+'\n')
    for row in rows: print(row['id'],row['status'])
    return int(any(r['status']!='prepared' for r in rows))
if __name__=='__main__':raise SystemExit(main())
