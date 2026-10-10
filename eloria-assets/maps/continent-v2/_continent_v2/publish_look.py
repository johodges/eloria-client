"""Derive every active isle's look from its pinned source-scene palettes.

The common terrain, grass, sky, water and foliage palette must agree across
contributing sources. Prop signature words are the stable union of those
sources; shared model identities remain intact. --check compares without writes.
Original profiles are read from Git so retirement cannot break regeneration.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import frames as F


def outputs(checkout):
    checkout=Path(checkout)
    catalog=json.loads((checkout/F.CATALOG).read_text())
    partition_path=F._res(catalog['partitionSpecPath'],checkout)
    partition=json.loads(partition_path.read_text())
    provenance=json.loads((partition_path.parent/'input-provenance.json').read_text())
    commit=provenance['sourceCommit']
    rows={r['mapId']:r for r in partition['sections']}
    result={}
    for region in F.regions(checkout):
        sources=sorted(rows[region]['placementsBySourceScene'])
        profiles=[]
        hashes={}
        for source in sources:
            path=f'godot-client/src/world/look/regions/{source}.json'
            raw=subprocess.check_output(['git','-C',str(checkout),'show',f'{commit}:{path}'])
            profiles.append(json.loads(raw))
            hashes[path]=hashlib.sha256(raw).hexdigest()
        base=copy.deepcopy(profiles[0])
        for key in ('schema','ground','grass','sky','water','foliage'):
            if any(p.get(key)!=base.get(key) for p in profiles[1:]):
                raise ValueError(f'{region}: contributing source palettes differ at {key}')
        base['id']=region
        base['props']={key:sorted({word for p in profiles for word in p.get('props',{}).get(key,[])})
                       for key in ('keep_words','hole_words')}
        base['notes']={'origin':'Derived from the frozen source palettes for this section; prop signature words '
                                 'retain the union of its contributing shared model libraries.',
                       'sourceCommit':commit,'sourceProfiles':hashes}
        result[checkout/f'godot-client/src/world/look/regions/{region}.json']=(
            json.dumps(base,indent='\t',ensure_ascii=False,allow_nan=False)+'\n').encode()
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkout',type=Path,default=F.DEFAULT_CHECKOUT)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    for path,raw in outputs(args.checkout).items():
        if args.check:
            if not path.is_file() or path.read_bytes()!=raw:
                raise ValueError(f'stale or missing look profile: {path}')
        else:
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(raw)
    print('all active catalog look profiles '+('verified' if args.check else 'generated'))


if __name__=='__main__':
    main()
