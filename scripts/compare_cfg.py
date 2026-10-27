#!/usr/bin/env python3
"""Compare directed CFG topology for source-owned, uniquely matched C functions."""
import argparse
import json
from pathlib import Path
import re
import signal
import networkx as nx

MARKER=re.compile(r'^\s*#\s*(\d+)\s+"([^"]+)"(?:\s+.*)?$')
def source_lines(text):
    path=None; original=None; mapping={}
    for physical,line in enumerate(text.splitlines(),1):
        match=MARKER.match(line)
        if match:
            path=match.group(2); original=int(match.group(1)); continue
        if path is not None:
            mapping[physical]=(path,original); original+=1
    return mapping

def identity(function, mapping, source):
    begin=function.get('start_line'); end=function.get('end_line')
    if not isinstance(begin,int) or not isinstance(end,int) or begin>end: return None
    entries=[mapping.get(i) for i in range(begin,end+1) if i in mapping]
    if not entries or any(Path(p).resolve()!=source for p,_ in entries): return None
    if begin not in mapping or end not in mapping: return None
    return (function['name'],mapping[begin][1],mapping[end][1])

def graph_from_cfg(cfg, reference):
    if reference:
        nodes=cfg['nodes']; edges=cfg['edges']; entries=cfg['entry']; exits=cfg['exit']
    else:
        nodes=[n['id'] for n in cfg['nodes']]; edges=cfg['edges']
        entries=[n['id'] for n in cfg['nodes'] if n['is_entrypoint']]
        exits=[n['id'] for n in cfg['nodes'] if n['is_exitpoint']]
    if len(nodes)!=len(set(nodes)) or not nodes: return None,'invalid_nodes'
    if len(entries)!=1 or not exits: return None,'missing_entry_or_exit'
    ids=set(nodes)
    if not set(entries+exits)<=ids or any(len(e)!=2 or e[0] not in ids or e[1] not in ids for e in edges): return None,'invalid_edges_or_roles'
    if len({tuple(edge) for edge in edges})!=len(edges): return None,'parallel_edges_unsupported'
    if len(nodes)>150: return None,'graph_too_large'
    graph=nx.DiGraph()
    graph.add_nodes_from((n,{'entry':n in entries,'exit':n in exits}) for n in nodes)
    graph.add_edges_from(edges)
    if len(nx.descendants(graph,entries[0]) | set(entries))!=len(nodes): return None,'unreachable_nodes'
    return graph,None

def compare_graphs(left,right,timeout):
    if left.number_of_nodes()!=right.number_of_nodes() or left.number_of_edges()!=right.number_of_edges(): return 'different'
    def expired(signum,frame): raise TimeoutError()
    previous=signal.signal(signal.SIGALRM,expired); signal.alarm(timeout)
    try:
        same=nx.is_isomorphic(left,right,node_match=lambda a,b:a['entry']==b['entry'] and a['exit']==b['exit'])
        return 'isomorphic' if same else 'different'
    except TimeoutError: return 'timeout'
    finally: signal.alarm(0); signal.signal(signal.SIGALRM,previous)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for a in ('prepared','source','native','reference','output','manifest','native-results'): p.add_argument('--'+a,type=Path,required=True)
    p.add_argument('--case-id',required=True)
    p.add_argument('--timeout',type=int,default=5); a=p.parse_args()
    if a.timeout<1: p.error('timeout must be positive')
    import hashlib
    content=a.prepared.read_bytes(); reference=json.loads(a.reference.read_text())
    input_sha=hashlib.sha256(content).hexdigest()
    matches=[r for r in json.loads(a.manifest.read_text())['cases'] if r['id']==a.case_id]
    results=[r for r in json.loads(a.native_results.read_text())['results'] if r['id']==a.case_id]
    if len(matches)!=1 or len(results)!=1: p.error('case must be unique in both manifests')
    case=matches[0]; result=results[0]
    if (input_sha!=reference['prepared_sha256'] or input_sha!=case.get('prepared_sha256')
            or input_sha!=result.get('prepared_sha256') or result.get('status')!='output'
            or hashlib.sha256(a.native.read_bytes()).hexdigest()!=result.get('graph_sha256')
            or hashlib.sha256(a.source.read_bytes()).hexdigest()!=case.get('source_sha256')):
        p.error('source, prepared input, reference or native graph hash mismatch')
    mapping=source_lines(content.decode()); source=a.source.resolve(); native=json.loads(a.native.read_text())
    # The upstream reference adapter exports a name-keyed map, so duplicates may
    # already be collapsed. This limits the population to unique C candidates.
    def collect(items):
        found={}
        for f in items:
            key=identity(f,mapping,source)
            if key is not None: found.setdefault(key,[]).append(f)
        return found
    a_map=collect(native['functions']); b_map=collect(reference['functions'].values()); rows=[]
    for key in sorted(set(a_map)|set(b_map)):
        left=a_map.get(key,[]); right=b_map.get(key,[]); row={'name':key[0],'source_start':key[1],'source_end':key[2]}
        if len(left)!=1 or len(right)!=1: row['status']='missing_or_ambiguous'
        else:
            ng,ne=graph_from_cfg(left[0]['cfg'],False); rg,re=graph_from_cfg(right[0]['cfg'],True)
            row.update(native_boundary=ne or 'bounded',reference_boundary=re or 'bounded')
            row['status']=compare_graphs(ng,rg,a.timeout) if ng is not None and rg is not None else 'unqualified'
        rows.append(row)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps({'prepared_sha256':input_sha,'source_sha256':case['source_sha256'],'native_graph_sha256':result['graph_sha256'],'native_backend_sha256':result['backend_sha256'],'reference_sha256':hashlib.sha256(a.reference.read_bytes()).hexdigest(),'scope':'observed source-owned candidates; not complete expected-function denominator','reference_identity_limit':'name-keyed capture may collapse duplicate names','rows':rows},indent=2)+'\n')
    from collections import Counter
    print(json.dumps(dict(Counter(row['status'] for row in rows)),sort_keys=True))
if __name__=='__main__':main()
