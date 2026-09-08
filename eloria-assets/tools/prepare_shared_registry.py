"""Measure shared body candidates and prepare their equipment registry in scratch."""
from __future__ import annotations
import argparse,copy,json,struct
from pathlib import Path
import equipment_authoring as ea
import import_generated_equipment as batch
import pack_canonical_equipment as pack
import verify_shared_player_bodies as verify


def doc_only(path):
    with path.open('rb') as stream:
        header=stream.read(20)
        if header[:4]!=b'glTF':raise ValueError(path)
        size=struct.unpack_from('<I',header,12)[0]
        return json.loads(stream.read(size))


def prepare(bodies,equipment_manifest,out):
    if out.exists():raise FileExistsError(out)
    if not out.resolve().is_relative_to(pack.SCRATCH.resolve()):raise ValueError('Use scratch output')
    inputs={key:(pack.ROOT/key).read_bytes() for key in [pack.REGISTRY.as_posix(),'godot-client/data/actors/models.json','godot-client/data/actors/native_asset_catalog.json']}
    registry=json.loads(inputs[pack.REGISTRY.as_posix()])
    models=json.loads(inputs['godot-client/data/actors/models.json'])
    catalog=json.loads(inputs['godot-client/data/actors/native_asset_catalog.json'])
    legacy=copy.deepcopy(registry['fitProfiles']['legacy'])
    manifest_raw=equipment_manifest.read_bytes();manifest=json.loads(manifest_raw)
    records={};templates={}
    for slug in sorted(catalog['races']):
        path=bodies/(slug+'.glb');template='luminous_'+slug.rsplit('_',1)[1]
        original=pack.SCRATCH/'shared-bodies/in'/(slug+'.glb')
        result=verify.verify(path,original,original.parent/(template+'.glb'))
        if result['errors']:raise ValueError((slug,result['errors']))
        before=verify.sha(path);rig=ea.load_rig(path,ea.BODY_SURFACES)
        girth=ea.body_girth(rig);anchors=ea.foot_anchor(rig)
        records[slug]={'sha256':before,'bodyTemplate':template,'bodyGirth':girth,'footAnchor':anchors,
                       'weightedSoles':{side:ea.weighted_sole(rig,side) for side in ('l','r')},
                       'headRestY':float(rig.origin('Head')[1]),'geometryVerification':result}
        if abs(records[slug]['headRestY']-ea.CANONICAL_HEAD_REST_Y)>1e-5:raise ValueError('Rest units changed')
        d,b=ea.read_glb(path)
        attributes={p['attributes']['POSITION'] for m in d['meshes'] for p in m['primitives']}
        entry=catalog['races'][slug]
        entry.update(vertices=sum(d['accessors'][i]['count'] for i in attributes),
                     triangles=sum(d['accessors'][p['indices']]['count']//3 for m in d['meshes'] for p in m['primitives']),
                     sha256=before,bodyTemplate=template,
                     retainedTailTriangles=result.get('trianglesByRole',{}).get('race_tail',0),
                     neckAdaptorTriangles=sum(result.get('trianglesByRole',{}).get(k,0) for k in ('neck_join','shared_neck')))
        models['models'][slug]['bodyTemplate']=template;templates[slug]=template
        if verify.sha(path)!=before:raise ValueError('Body changed during measurement')
        print(slug,'measured',flush=True)
    registry['bodyTemplates']=templates
    registry['canonicalHeadRestY']=ea.CANONICAL_HEAD_REST_Y
    for key in ('bodyGirth','footAnchor'):registry[key]={s:r[key] for s,r in records.items()}
    registry['soleDrop']={s:{bone:round(-a[1],5) for bone,a in r['footAnchor'].items() if a[1]<-.0001} for s,r in records.items()}
    for slug,template in templates.items():
        groups=['canonical_'+slug]
        if slug.endswith('_female') and slug!=template:groups.append('canonical_'+template)
        registry['fitGroups'][slug]=groups
    for piece in batch.roster():
        if piece.part==3:continue
        row=registry['models'][f'{piece.part}:{piece.visual}']
        row['variants']={'canonical_luminous_female':row['variants']['canonical_luminous_female']}
    assert registry['fitProfiles']['legacy']==legacy
    # Refresh the validation inventory for the planned, explicit removal of old
    # body variants. Other native assets remain in the inventory unchanged.
    parent=json.loads(Path(manifest['parent_manifest']).read_bytes())
    retained=set(manifest['files'])
    removed={k for k in parent['files'] if k not in retained and k.endswith('.glb')}
    paths={p.relative_to(pack.ROOT).as_posix():p for p in (pack.ROOT/'godot-client/assets/actors/native').rglob('*.glb')}
    for key in removed:paths.pop(key,None)
    for key in retained:
        if key.endswith('.glb'):paths[key]=equipment_manifest.parent/key
    for slug in templates:paths[f'godot-client/assets/actors/native/races/{slug}.glb']=bodies/(slug+'.glb')
    results={}
    for key,path in sorted(paths.items()):
        d=doc_only(path);results[key]={k:len(d.get(k,[])) for k in ('nodes','meshes','skins','animations')}
    catalog['validation']={'files':len(results),'results':results}
    outputs={pack.REGISTRY.as_posix():registry,'godot-client/data/actors/models.json':models,'godot-client/data/actors/native_asset_catalog.json':catalog}
    for key,value in outputs.items():pack.new_file(out/key,(json.dumps(value,indent=2)+'\n').encode())
    preview=copy.deepcopy(registry)
    for row in preview['models'].values():
        for value in [row,*row.get('variants',{}).values()]:
            path='godot-client/'+value['scene'].removeprefix('res://')
            if path in retained:value['scene']=(equipment_manifest.parent/path).resolve().as_posix()
    pack.new_file(out/'preview-equipment.json',(json.dumps(preview,indent=2)+'\n').encode())
    pack.new_file(out/'measurements.json',(json.dumps(records,indent=2)+'\n').encode())
    for key,raw in inputs.items():
        if (pack.ROOT/key).read_bytes()!=raw:raise ValueError('Registry changed during preparation')
    if equipment_manifest.read_bytes()!=manifest_raw:raise ValueError('Equipment pack changed')
    report={'inputs':{k:pack.sha(v) for k,v in inputs.items()},'equipment_manifest_sha256':pack.sha(manifest_raw),
            'bodies':{s:r['sha256'] for s,r in records.items()},'outputs':{k:verify.sha(out/k) for k in outputs},
            'tool_sha256':verify.sha(__file__)}
    pack.new_file(out/'manifest.json',(json.dumps(report,indent=2)+'\n').encode())
    return report


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--bodies',type=Path,required=True);ap.add_argument('--equipment-manifest',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();prepare(args.bodies,args.equipment_manifest,args.out)
