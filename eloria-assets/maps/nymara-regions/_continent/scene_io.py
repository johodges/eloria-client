"""Lossless static-scene partitioning over the shared toolkit glTF reader.

Referenced vertex buffers are copied once, image bytes are content-addressed,
and object hierarchies remain whole. A selection never serialises unselected
mesh buffers. Generated world transforms live on wrappers so animations and
the original authored local transforms remain valid.
"""
from __future__ import annotations
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import sys
import numpy as np
from PIL import Image

TOOLKIT=Path(__file__).resolve().parents[1]/'_toolkit'
if str(TOOLKIT) not in sys.path: sys.path.insert(0,str(TOOLKIT))
import glb_reader as GR


def dump_glb(path, document, body):
    document=copy.deepcopy(document)
    document['buffers']=[{'byteLength':len(body)}]
    raw=json.dumps(document,separators=(',',':'),ensure_ascii=False).encode()
    raw+=b' '*((-len(raw))%4)
    body=bytes(body)+b'\0'*((-len(body))%4)
    header=struct.pack('<4sII',b'glTF',2,12+8+len(raw)+8+len(body))
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(header+struct.pack('<II',len(raw),0x4E4F534A)+raw+struct.pack('<II',len(body),0x004E4942)+body)


def descendants(document, roots):
    included=set()
    def visit(index):
        if index in included: return
        included.add(index)
        for child in document['nodes'][index].get('children',[]): visit(child)
    for root in roots: visit(root)
    return included


def subtree_bounds(document, body, root, matrices=None):
    matrices=GR.hierarchy(document)[0] if matrices is None else matrices
    lo=np.full(3,np.inf);hi=-lo
    for index in descendants(document,[root]):
        node=document['nodes'][index]
        if 'mesh' not in node: continue
        for p in document['meshes'][node['mesh']]['primitives']:
            a=document['accessors'][p['attributes']['POSITION']]
            if 'min' in a and 'max' in a:
                low,high=np.array(a['min']),np.array(a['max'])
                v=np.array([[x,y,z] for x in (low[0],high[0]) for y in (low[1],high[1]) for z in (low[2],high[2])])
            else: v=GR.accessor(document,body,p['attributes']['POSITION'])
            m=matrices[index];v=v@m[:3,:3].T+m[:3,3]
            lo=np.minimum(lo,v.min(axis=0));hi=np.maximum(hi,v.max(axis=0))
    if not np.isfinite(lo).all(): lo=hi=matrices[root][:3,3].copy()
    return lo,hi


class Exporter:
    def __init__(self, path, shared_images=None):
        self.path=Path(path)
        self.shared_images=Path(shared_images) if shared_images else None
        self.doc={'asset':{'version':'2.0','generator':'Eloria shared continent partitioner'},
                  'scene':0,'scenes':[{'nodes':[]}],'nodes':[],'meshes':[],
                  'materials':[],'textures':[],'images':[],'samplers':[],
                  'accessors':[],'bufferViews':[]}
        self.body=bytearray()
        self.memo={}
        self.image_memo={}
        self.dependencies={}
        self.resource_bytes={}

    def view(self, data, template=None):
        self.body.extend(b'\0'*((-len(self.body))%4))
        out=copy.deepcopy(template or {})
        out.update(buffer=0,byteOffset=len(self.body),byteLength=len(data))
        self.body.extend(data)
        self.doc['bufferViews'].append(out)
        return len(self.doc['bufferViews'])-1

    def add(self, source, body, roots, *, transforms=None, prefix='', node_prefix=''):
        """Add selected root subtrees; transforms are XYZ offsets per source root."""
        identity=id(source)
        def transfer(kind,index):
            key=(identity,kind,index)
            if key in self.memo: return self.memo[key]
            old=source[kind][index]
            out=copy.deepcopy(old)
            if kind=='bufferViews':
                start=old.get('byteOffset',0)
                result=self.view(body[start:start+old['byteLength']],old)
                self.memo[key]=result;return result
            if kind=='accessors':
                if 'sparse' in old: raise ValueError('Sparse accessors need explicit partition support')
                if 'bufferView' in old: out['bufferView']=transfer('bufferViews',old['bufferView'])
            elif kind=='meshes':
                for part in out['primitives']:
                    part['attributes']={k:transfer('accessors',v) for k,v in part['attributes'].items()}
                    if 'indices' in part: part['indices']=transfer('accessors',part['indices'])
                    if 'material' in part: part['material']=transfer('materials',part['material'])
                    if 'targets' in part: part['targets']=[{k:transfer('accessors',v) for k,v in t.items()} for t in part['targets']]
            elif kind=='materials':
                def textures(item):
                    if isinstance(item,dict):
                        for k,v in item.items():
                            if k.endswith('Texture') and isinstance(v,dict) and 'index' in v: v['index']=transfer('textures',v['index'])
                            else: textures(v)
                    elif isinstance(item,list):
                        for v in item: textures(v)
                textures(out)
            elif kind=='textures':
                if 'source' in out: out['source']=transfer('images',out['source'])
                if 'sampler' in out: out['sampler']=transfer('samplers',out['sampler'])
            elif kind=='images':
                if 'bufferView' not in old: raise ValueError('Library images must be embedded and certified')
                view=source['bufferViews'][old['bufferView']]
                start=view.get('byteOffset',0);data=body[start:start+view['byteLength']]
                sha=hashlib.sha256(data).hexdigest()
                if sha not in self.resource_bytes:
                    with Image.open(io.BytesIO(data)) as picture:
                        self.resource_bytes[sha]=int(np.ceil(picture.width*picture.height*4*4/3))
                if sha in self.image_memo:
                    result=self.image_memo[sha];self.memo[key]=result;return result
                if self.shared_images:
                    self.shared_images.mkdir(parents=True,exist_ok=True)
                    suffix='.png' if old.get('mimeType','image/png')=='image/png' else '.jpg'
                    target=self.shared_images/(sha+suffix)
                    if not target.exists(): target.write_bytes(data)
                    elif hashlib.sha256(target.read_bytes()).hexdigest()!=sha: raise ValueError('Shared image digest mismatch')
                    uri=os.path.relpath(target,self.path.parent).replace('\\','/')
                    out={'uri':uri,'name':old.get('name',sha)}
                    self.dependencies[uri]=sha
                else: out['bufferView']=self.view(data)
            result=len(self.doc[kind]);self.doc[kind].append(out);self.memo[key]=result
            if kind=='images': self.image_memo[sha]=result
            return result
        chosen=descendants(source,roots)
        mapping={old:len(self.doc['nodes'])+i for i,old in enumerate(sorted(chosen))}
        for old_index in sorted(chosen):
            node=copy.deepcopy(source['nodes'][old_index])
            if node_prefix and 'name' in node:
                name=node['name']
                node['name']=('Walk_'+node_prefix+name[5:]) if name.startswith('Walk_') else node_prefix+name
            if 'skin' in node: raise ValueError('World scenery must not contain character skins')
            if 'mesh' in node: node['mesh']=transfer('meshes',node['mesh'])
            if 'children' in node: node['children']=[mapping[c] for c in node['children'] if c in chosen]
            self.doc['nodes'].append(node)
        for root in roots:
            child=mapping[root]
            shift=(transforms or {}).get(root,[0,0,0])
            wrapper={'name':prefix+node_prefix+source['nodes'][root].get('name',str(root))+'_WorldPlacement',
                     'translation':list(map(float,shift)),'children':[child]}
            self.doc['scenes'][0]['nodes'].append(len(self.doc['nodes']))
            self.doc['nodes'].append(wrapper)
        for animation in source.get('animations',[]):
            channels=[copy.deepcopy(c) for c in animation.get('channels',[]) if c['target'].get('node') in mapping]
            if not channels: continue
            out={'name':animation.get('name','Motion'),'channels':channels,'samplers':[]}
            for c in channels:
                c['target']['node']=mapping[c['target']['node']]
                s=copy.deepcopy(animation['samplers'][c['sampler']])
                s['input']=transfer('accessors',s['input']);s['output']=transfer('accessors',s['output'])
                c['sampler']=len(out['samplers']);out['samplers'].append(s)
            self.doc.setdefault('animations',[]).append(out)
        for field in ('extensionsUsed','extensionsRequired'):
            if source.get(field): self.doc[field]=sorted(set(self.doc.get(field,[]))|set(source[field]))

    def write(self):
        dump_glb(self.path,self.doc,self.body)
        return {'glbBytes':self.path.stat().st_size,'nodes':len(self.doc['nodes']),
                'meshes':len(self.doc['meshes']),'externalResources':self.dependencies,
                'sharedResourceResidentBytes':self.resource_bytes}
