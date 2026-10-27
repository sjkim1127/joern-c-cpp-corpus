#!/usr/bin/env python3
"""Preprocess pinned zlib inputs under explicit experimental C standard modes."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import struct

ROOT=Path(__file__).resolve().parents[1]
REV='51b7f2abdade71cd9bb0e7a373ef2610ec6f9daf'
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''): h.update(block)
    return h.hexdigest()

def object_identity(path):
    data=path.read_bytes()[:64]
    if len(data)<20: return None
    if data[:4]==b'\x7fELF':
        endian='<' if data[5]==1 else '>' if data[5]==2 else None
        if not endian: return None
        machine=struct.unpack(endian+'H',data[18:20])[0]
        return {'format':'ELF','architecture':{3:'x86',62:'x86_64',183:'aarch64'}.get(machine,'unknown'),'machine':machine}
    magic=data[:4]
    if magic in (b'\xcf\xfa\xed\xfe',b'\xce\xfa\xed\xfe'):
        cpu=struct.unpack('<I',data[4:8])[0]
        return {'format':'Mach-O','architecture':{7:'x86',0x1000007:'x86_64',0x100000c:'aarch64'}.get(cpu,'unknown'),'machine':cpu}
    machine=struct.unpack('<H',data[:2])[0]
    if machine in (0x14c,0x8664,0xaa64): return {'format':'COFF','architecture':{0x14c:'x86',0x8664:'x86_64',0xaa64:'aarch64'}[machine],'machine':machine}
    return None

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkout',type=Path,required=True)
    p.add_argument('--compiler',type=Path,required=True)
    p.add_argument('--standard',choices=['c11','c17','c23'],action='append',required=True)
    p.add_argument('--output-dir',type=Path,default=ROOT/'workspace/prepared')
    p.add_argument('--preserve-linemarkers',action='store_true')
    p.add_argument('--source',action='append',help='Select source filename; repeat to add more')
    p.add_argument('--compiler-target',help='Clang target triple, e.g. x86_64-apple-macos13')
    p.add_argument('--sysroot',type=Path,help='Explicit compiler sysroot or SDK')
    p.add_argument('--verify-object',action='store_true')
    p.add_argument('--expected-format',choices=['ELF','COFF','Mach-O'])
    p.add_argument('--expected-arch',choices=['x86','x86_64','aarch64'])
    args=p.parse_args()
    if args.verify_object and not (args.expected_format and args.expected_arch): p.error('--verify-object requires expected format and architecture')
    checkout=args.checkout.resolve(); compiler=args.compiler.resolve()
    def git(*args): return subprocess.check_output(['git','-C',str(checkout),*args],text=True).strip()
    if git('rev-parse','HEAD')!=REV or git('status','--porcelain','--untracked-files=all'):
        p.error('checkout must be clean at the pinned zlib commit')
    compiler_version=subprocess.check_output([str(compiler),'--version'],text=True).splitlines()[0]
    target_flags=['--target='+args.compiler_target] if args.compiler_target else []
    target=subprocess.check_output([str(compiler),*target_flags,'-dumpmachine'],text=True).strip()
    entries=[e for e in json.loads((ROOT/'manifests/inputs.json').read_text())['entries'] if e['project']=='zlib']
    if args.source:
        selected=set(args.source); entries=[e for e in entries if e['source_path'] in selected]
        if {e['source_path'] for e in entries}!=selected: p.error('unknown source selection')
    output=args.output_dir.resolve(); output.mkdir(parents=True,exist_ok=True)
    rows=[]
    for standard in dict.fromkeys(args.standard):
        for entry in entries:
            source=checkout/entry['source_path']; dest=output/f"{entry['id']}-{standard}.i"
            row={'id':f"{entry['id']}-{standard}",'source_id':entry['id'],'source_revision':REV,'source_sha256':sha(source),'language':'c','standard':standard,'standard_origin':'explicit experimental mode; not original project build', 'compiler_path':str(compiler),'compiler_sha256':sha(compiler),'compiler_version':compiler_version,'target':target,'platform':platform.platform(),'flags':[*target_flags,*(['-isysroot',str(args.sysroot.resolve())] if args.sysroot else []),'-std='+standard,'-I',str(checkout)],'preprocess_flags':(['-E'] if args.preserve_linemarkers else ['-E','-P']),'syntax_flags':['-fsyntax-only'], 'prepared_source':str(dest)}
            if row['source_sha256']!=entry['sha256']:
                row.update(status='source_hash_mismatch'); rows.append(row); continue
            flags=row['flags']
            syntax=subprocess.run([str(compiler),*flags,'-fsyntax-only',str(source)],capture_output=True,text=True)
            row['syntax_returncode']=syntax.returncode; row['syntax_stderr']=syntax.stderr[-3000:]
            if syntax.returncode:
                row['status']='compiler_rejected'; rows.append(row); continue
            prep=subprocess.run([str(compiler),*flags,*row['preprocess_flags'],str(source)],capture_output=True)
            if prep.returncode:
                row.update(status='preprocess_error',preprocess_stderr=prep.stderr.decode(errors='replace')[-3000:]); rows.append(row); continue
            dest.write_bytes(prep.stdout); row.update(status='prepared',prepared_sha256=sha(dest),prepared_size=len(prep.stdout))
            if args.verify_object:
                obj=output/f"{entry['id']}-{standard}.o"
                built=subprocess.run([str(compiler),*flags,'-c',str(source),'-o',str(obj)],capture_output=True,text=True)
                row['object_returncode']=built.returncode; row['object_expected']={'format':args.expected_format,'architecture':args.expected_arch}
                if built.returncode:
                    row.update(status='object_compile_error',object_stderr=built.stderr[-3000:])
                else:
                    row['object_sha256']=sha(obj); row['object_identity']=object_identity(obj)
                    if row['object_identity'] is None: row['status']='object_format_unrecognized'
                    elif row['object_identity']['format']!=args.expected_format or row['object_identity']['architecture']!=args.expected_arch: row['status']='object_target_mismatch'
            rows.append(row)
    manifest=output/'manifest.json'; manifest.write_text(json.dumps({'schema_version':1,'cases':rows},indent=2)+'\n')
    for row in rows: print(row['id'],row['status'])
    print('manifest:',manifest)
    return 0 if all(r['status']=='prepared' for r in rows) else 1
if __name__=='__main__': sys.exit(main())
