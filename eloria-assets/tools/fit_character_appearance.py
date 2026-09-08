"""Fit wardrobe and authored hair to an assembled canonical body.

Writes review candidates to a separate directory. Skeletons, skin, textures and
non-shirt garments are preserved. Shader normal-grow is baked using a welded
displacement field, retaining the source's faceted shading without tearing UV
or material seams. The collar follows the reconstructed neck and its weights.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys

import numpy as np
import trimesh
from scipy.spatial import cKDTree

import equipment_authoring as ea
from shared_player_bodies import append_array, dense_weights, sparse_weights, clip, write_group, append_view
from verify_shared_player_bodies import primitives, sha
sys.path.insert(0, str(Path(__file__).parent / "tpose_bodies/vendor"))
import glbkit as g


def unit(v):
    return v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-12)


def weld(points):
    # Clipping creates copies across material and UV boundaries with float32
    # roundoff. Use proximity, rather than rounding bins that split close pairs.
    parent = np.arange(len(points))
    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i, j in sorted(cKDTree(points).query_pairs(2e-6)):
        a, b = root(i), root(j)
        parent[max(a, b)] = min(a, b)
    return np.unique([root(i) for i in range(len(points))], return_inverse=True)[1]


def average(values, groups):
    result = np.zeros((groups.max()+1, values.shape[1]))
    np.add.at(result, groups, values)
    result /= np.bincount(groups)[:, None]
    return result[groups]


def ray_surface(mesh, origins, directions):
    locations, rays, triangles = mesh.ray.intersects_location(
        origins, directions, multiple_hits=True)
    distance = np.full(len(origins), -np.inf)
    hit_face = np.full(len(origins), -1, dtype=int)
    hit_point = np.zeros_like(origins)
    lengths = np.einsum('ij,ij->i', locations-origins[rays], directions[rays])
    # Outermost hit closes cracks even where a source contains internal faces.
    for index in np.argsort(lengths):
        ray = rays[index]
        distance[ray] = lengths[index]
        hit_face[ray] = triangles[index]
        hit_point[ray] = locations[index]
    return distance, hit_face, hit_point


def combined(parts):
    arrays, faces, offset = [], [], 0
    for _, _, a, f in parts:
        ids = np.unique(f)
        remap = np.full(len(a['POSITION']), -1)
        remap[ids] = np.arange(len(ids))
        arrays.append({k: v[ids] for k, v in a.items()})
        faces.append(remap[f]+offset)
        offset += len(ids)
    return {k: np.concatenate([a[k] for a in arrays]) for k in arrays[0]}, np.concatenate(faces)


def fit_shirt(d, binary):
    parts = list(primitives(d, bytes(binary)))
    a, faces = combined([p for p in parts if p[0] == 'wardrobe_shirt'])
    original = a['POSITION'].copy()
    groups = weld(original)
    v = average(original, groups)
    normals = unit(average(a['NORMAL'], groups))
    # Average complete distributions before reducing to four weights, so UV
    # seams remain closed in animation as well as the rest pose.
    weights = average(dense_weights(a), groups)
    moved = v + .011 * normals
    skin, sf = combined([p for p in parts if p[0] == 'body' and p[1]=='neck_join'])
    world = ea.global_matrices(d)
    neck = next(i for i,n in enumerate(d['nodes']) if n.get('name') == 'neck_01')
    head = next(i for i,n in enumerate(d['nodes']) if n.get('name') == 'Head')
    origin = world[neck][:3,3]
    axis = world[head][:3,3]-origin
    axis /= np.linalg.norm(axis)
    height = (v-origin)@axis
    centres = origin + height[:,None]*axis
    radial = v-centres
    radius = np.linalg.norm(radial,axis=1)
    collar = np.flatnonzero((height > -.085) & (radius < .18))
    mesh = trimesh.Trimesh(skin['POSITION'], sf, process=False)
    direction = unit(radial[collar])
    near_axis = radius[collar] < .025
    outward = normals[collar] - (normals[collar]@axis)[:,None]*axis
    direction[near_axis] = unit(outward[near_axis])
    distance, face, hit = ray_surface(mesh, centres[collar], direction)
    valid = face >= 0
    collar, distance, face, hit, direction = (
        x[valid] for x in (collar,distance,face,hit,direction))
    current_radius = np.einsum('ij,ij->i', moved[collar]-centres[collar], direction)
    # The source also has folded inner collar faces close to the neck axis.
    # They must not be projected across the entire torso to the opposite wall.
    deficit = np.clip(distance + .012-current_radius, 0, .045)
    moved[collar] += deficit[:,None]*direction
    # Skin under the collar is reconstructed independently of the old shirt.
    # Follow its deformation near contact, fading into the original shoulder.
    bary = trimesh.triangles.points_to_barycentric(mesh.triangles[face],hit)
    skin_weights = dense_weights(skin)
    target_weights = np.einsum('ij,ijk->ik', bary, skin_weights[sf[face]])
    blend = np.clip((height[collar]+.025)/.06, 0, 1)
    blend = blend*blend*(3-2*blend)
    weights[collar] = weights[collar]*(1-blend[:,None])+target_weights*blend[:,None]
    moved = average(moved, groups)
    weights = average(weights, groups)
    a['POSITION'] = moved.astype('<f4')
    a['JOINTS_0'], a['WEIGHTS_0'] = sparse_weights(weights)
    # Each primitive gets a compact private attribute set; changing a shared
    # POSITION accessor would also move the exposed body and other garments.
    cursor = 0
    shirt = next(m for m in d['meshes'] if m['name']=='wardrobe_shirt')
    for p, source in zip(shirt['primitives'],[p for p in parts if p[0]=='wardrobe_shirt']):
        ids = np.unique(source[3]); count = len(ids)
        remap = np.full(len(source[2]['POSITION']),-1);remap[ids]=np.arange(count)
        p['attributes'] = {k: append_array(d,binary,value[cursor:cursor+count],
            'VEC'+str(value.shape[1]),5123 if k=='JOINTS_0' else 5126)
            for k,value in a.items() if k != 'TANGENT'}
        p['indices'] = append_array(d,binary,remap[source[3]].ravel(),'SCALAR',5125)
        cursor += count
    # Close small internal holes in the source; retain the collar, cuffs and
    # hem openings. Isolated source triangles are details, not missing faces.
    gf=groups[faces]
    directed=np.concatenate([gf[:,[0,1]],gf[:,[1,2]],gf[:,[2,0]]])
    edges,first,counts=np.unique(np.sort(directed,axis=1),axis=0,return_index=True,return_counts=True)
    boundary=directed[first[counts==1]]
    _,representatives=np.unique(groups,return_index=True)
    patches=[]
    for component in trimesh.graph.connected_components(boundary,min_len=1):
        if len(component)>18 or np.abs(v[representatives[component],0]).max()>.69:
            continue
        if np.isin(gf,component).all(1).any():
            continue
        links=boundary[np.isin(boundary,component).all(1)]
        if len(links)!=len(component):continue
        following={int(x):int(y) for x,y in links}
        if len(following)!=len(component):continue
        loop=[int(component[0])]
        while len(loop)<len(component) and loop[-1] in following:
            nxt=following[loop[-1]]
            if nxt in loop:break
            loop.append(nxt)
        if len(loop)!=len(component):continue
        ids=representatives[loop]
        for i in range(1,len(ids)-1):patches.append([ids[0],ids[i+1],ids[i]])
    if patches:
        repairs={'a':{k:value for k,value in a.items() if k!='TANGENT'},
            'f':{('wardrobe_shirt',shirt['primitives'][0]['material']):np.array(patches)},
            'role':'wardrobe_repairs'}
        repair_meshes={};write_group(d,binary,repairs,repair_meshes)
        shirt['primitives']+=repair_meshes['wardrobe_shirt']
    # A narrow fitted facing sits beneath the old collar, whose source opening
    # extends down the back. It covers the reconstructed neck below the collar
    # while preserving the lower V at the throat. It shares the neck's weights.
    relative=skin['POSITION']-origin
    travel=relative@axis
    radial=relative-travel[:,None]*axis
    forward=unit(radial)@np.array([0.,0.,1.])
    neckline=.0375-.0375*forward
    lining=clip({'a':skin,'f':{('wardrobe_shirt',0):sf}},travel-neckline,False)
    lining_groups=weld(lining['a']['POSITION'])
    lining['a']['POSITION']=(lining['a']['POSITION']+.006*unit(average(lining['a']['NORMAL'],lining_groups))).astype('<f4')
    # A neutral cloth texel tints with the other primitives without sampling
    # the skin atlas that the anatomical neck uses.
    import io
    from PIL import Image
    encoded=io.BytesIO();Image.new('RGB',(1,1),(235,235,235)).save(encoded,format='PNG')
    d['images'].append({'mimeType':'image/png','bufferView':append_view(d,binary,encoded.getvalue())})
    d['textures'].append({'source':len(d['images'])-1})
    d['materials'].append({'name':'Collar facing','doubleSided':True,'pbrMetallicRoughness':{
        'baseColorTexture':{'index':len(d['textures'])-1},'metallicFactor':0.,'roughnessFactor':.85}})
    lining['f']={('wardrobe_shirt',len(d['materials'])-1):next(iter(lining['f'].values()))}
    lining['role']='wardrobe_lining'
    lining_meshes={};write_group(d,binary,lining,lining_meshes)
    shirt['primitives']+=lining_meshes['wardrobe_shirt']
    return {'vertices':len(v),'weldedVertices':int(groups.max()+1),
        'patchedTriangles':len(patches),'liningTriangles':len(next(iter(lining['f'].values()))),
        'collarPushedVertices':int((deficit>0).sum()),
        'maximumDisplacementM':float(np.linalg.norm(moved-original,axis=1).max())}


def head_data(d,b):
    parts = [p for p in primitives(d,b) if p[1]=='race_head']
    a,f=combined(parts)
    hi=next(i for i,n in enumerate(d['nodes']) if n.get('name')=='Head')
    matrix=ea.global_matrices(d)[hi]
    v=(a['POSITION']-matrix[:3,3])@matrix[:3,:3]
    return trimesh.Trimesh(v,f,process=False), dense_weights(a), matrix


def fit_hair(source, out, head, base_fit, body, body_binary):
    skull, skull_weights, head_matrix = head
    d,b=g.read(source);binary=bytearray(b)
    scale=np.array(base_fit['scale']);offset=np.array(base_fit['offset'])
    # Reference caps have different crown heights. Use each style's crown,
    # excluding side buns and long locks from the measurement.
    p=d['meshes'][0]['primitives'][0]
    raw=g.accessor(d,b,p['attributes']['POSITION'])
    skull_core=skull.vertices[(abs(skull.vertices[:,0])<.045)&(skull.vertices[:,1]>.07)]
    top=np.percentile(skull_core[:,1],99)
    cap=raw[(abs(raw[:,0])<.04)&(abs(raw[:,2])<.055)]
    scale[1]=(top+.007)/cap[:,1].max()
    centre=np.array([offset[0],top-.075,offset[2]])
    maximum=0.
    for mesh in d['meshes']:
        for p in mesh['primitives']:
            attributes={k:g.accessor(d,b,index) for k,index in p['attributes'].items()}
            f=g.accessor(d,b,p['indices']).astype(int).reshape(-1,3)
            # Curved skulls and raised scales can emerge between the original
            # cap's vertices. Subdivide without changing the authored UVs or
            # silhouette, then fit those extra surface samples too.
            edges=np.sort(np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]),axis=1)
            unique,inverse=np.unique(edges,axis=0,return_inverse=True)
            midpoint=inverse.reshape(3,-1).T+len(attributes['POSITION'])
            for k,values in attributes.items():
                attributes[k]=np.concatenate([values,values[unique].mean(1)])
            a0,b0,c0=f.T;ab,bc,ca=midpoint.T
            f=np.concatenate([np.stack([a0,ab,ca],1),np.stack([b0,bc,ab],1),
                np.stack([c0,ca,bc],1),np.stack([ab,bc,ca],1)])
            v=attributes['POSITION']*scale+offset
            direction=unit(v-centre)
            distance,_,_=ray_surface(skull,np.broadcast_to(centre,v.shape),direction)
            radius=np.linalg.norm(v-centre,axis=1)
            push=np.maximum(distance+.010-radius,0)
            push[~np.isfinite(push)]=0
            maximum=max(maximum,float(push.max()))
            v+=push[:,None]*direction
            groups=weld(v)
            v=average(v,groups)
            _, _, nearest = trimesh.proximity.closest_point(skull, v)
            closest = trimesh.triangles.closest_point(skull.triangles[nearest], v)
            bary = trimesh.triangles.points_to_barycentric(skull.triangles[nearest],closest)
            weights = np.einsum('ij,ijk->ik',bary,skull_weights[skull.faces[nearest]])
            joints,weights=sparse_weights(average(weights,groups))
            # Area-weighted normals shared at UV seams, with existing UVs and
            # all authored faces retained.
            face_normal=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]])
            n=np.zeros_like(v)
            for c in range(3):np.add.at(n,f[:,c],face_normal)
            n=unit(average(n,groups))
            v=v@head_matrix[:3,:3].T+head_matrix[:3,3]
            n=n@head_matrix[:3,:3].T
            p['attributes']['POSITION']=append_array(d,binary,v.astype('<f4'),'VEC3',5126)
            p['attributes']['NORMAL']=append_array(d,binary,n.astype('<f4'),'VEC3',5126)
            p['attributes']['JOINTS_0']=append_array(d,binary,joints,'VEC4',5123)
            p['attributes']['WEIGHTS_0']=append_array(d,binary,weights,'VEC4',5126)
            p['attributes'].pop('TANGENT',None)
            for k,values in attributes.items():
                if k not in ('POSITION','NORMAL','TANGENT'):
                    p['attributes'][k]=append_array(d,binary,values.astype('<f4'),'VEC'+str(values.shape[1]),5126)
            p['indices']=append_array(d,binary,f.ravel(),'SCALAR',5125)
    # Hair follows the same weighted head surface as the skin. A rigid Head
    # attachment pulls away from occipital vertices blended with neck_01.
    node_offset=len(d['nodes'])
    for node in d['nodes']:
        if 'mesh' in node:node['skin']=0
    for source_node in body['nodes']:
        node=copy.deepcopy(source_node)
        node.pop('mesh',None);node.pop('skin',None)
        if 'children' in node:node['children']=[i+node_offset for i in node['children']]
        d['nodes'].append(node)
    source_skin=body['skins'][0]
    skin=copy.deepcopy(source_skin)
    skin['joints']=[i+node_offset for i in source_skin['joints']]
    if 'skeleton' in skin:skin['skeleton']+=node_offset
    binds=ea.accessor_array(body,body_binary,source_skin['inverseBindMatrices'])
    skin['inverseBindMatrices']=append_array(d,binary,binds,'MAT4',5126)
    d['skins']=[skin]
    d['scenes'][d.get('scene',0)]['nodes'] += [i+node_offset for i in body['scenes'][body.get('scene',0)]['nodes']]
    d.setdefault('asset',{}).setdefault('extras',{})['headFit']={
        'sourceSHA256':sha(source),'clearanceM':.010}
    d,binary=g.compact(d,bytes(binary));g.write(out,d,binary)
    return {'source':str(source),'sha256':sha(out),'maxRadialCorrectionM':maximum}


def run(model, config, hair_root, out):
    if 'godot-client' in out.resolve().parts or (out/model.name).resolve()==model.resolve():
        raise ValueError('Use a separate scratch output; review before installing')
    out.mkdir(parents=True,exist_ok=True)
    d,b=g.read(model);binary=bytearray(b)
    if d['asset'].get('extras',{}).get('appearanceFit'):
        raise ValueError('Use the original input snapshot, not an already fitted output')
    head=head_data(d,b)
    body=copy.deepcopy(d)
    report={'sourceSHA256':sha(model),'shirt':fit_shirt(d,binary),'hair':{}}
    d['asset'].setdefault('extras',{})['appearanceFit']={'version':1,'bakedShirtGrowM':.011}
    d,binary=g.compact(d,bytes(binary));g.write(out/model.name,d,binary)
    styles=list(config['hairStyles'])
    for style in range(1,len(styles)):
        source=hair_root/Path(styles[style]).name
        target=out/(model.stem+'_'+source.name)
        report['hair'][str(style)]=fit_hair(source,target,head,config['hairFit'],body,b)
        styles[style]=str(target.resolve()).replace('\\','/')
    candidate={'hairStyles':styles,'hairFit':{},'hairSkinned':True,'wardrobeBakedGrow':['wardrobe_shirt']}
    (out/(model.stem+'.config.json')).write_text(json.dumps(candidate,indent=2)+'\n')
    (out/(model.stem+'.report.json')).write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--model',type=Path,required=True)
    ap.add_argument('--models',type=Path,required=True)
    ap.add_argument('--hair-root',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    config=json.loads(args.models.read_text())['models'][args.model.stem]
    print(json.dumps(run(args.model,config,args.hair_root,args.out)))
