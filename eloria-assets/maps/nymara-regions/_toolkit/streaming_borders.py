"""Authored, reciprocal road collars for exterior scene streaming.

Coordinates are tile centres. The seam sits one metre inward from the trigger;
the two-metre arrival offset therefore preserves the traveller's world position.
Overflow remains in the collision survey and is hidden only while its real
neighbour is resident. No server or rendered walking surface is invented at run time.
"""
import numpy as np
from amberwood.mesh import rotation_y
from amberwood.terrain import _compact

# Each pair shares its surface recipe and road-space texture coordinates.
# Frames are local: the client carries the traveller/camera between them.
LINKS = [
 ('amberwood-whitehorn', ('amberwood','north-pass',[67.5,55.2,-256.5],[0,-1]),
  ('whitehorn_range','west-pass',[-106.5,35.8,-54.5],[-1,0]), 'alpine'),
 ('amberwood-grey', ('amberwood','south-road',[122.5,11.1,107.5],[0,1]),
  ('grey_moors','north-gate',[-8.5,4,-256.5],[0,-1]), 'moor'),
 ('amberwood-mirrorhold', ('amberwood','east-road',[261.5,41.8,-28.5],[1,0]),
  ('mirrorhold','west-gorge',[-110.5,24,20.5],[-1,0]), 'upland'),
 ('whitehorn-mirrorhold', ('whitehorn_range','south-gate',[-1.5,12.1,107.5],[0,1]),
  ('mirrorhold','north-pass',[-76.5,85,-281.5],[0,-1]), 'alpine'),
 ('whitehorn-amethyst', ('whitehorn_range','east-pass',[260.5,36.1,-30.5],[1,0]),
  ('amethyst_barrens','north-pass',[54.5,12,-261.5],[0,-1]), 'scree'),
 ('mirrorhold-amethyst', ('mirrorhold','east-road',[10.5,93,-281.5],[0,-1]),
  ('amethyst_barrens','west-road',[-110.5,8,-192.5],[-1,0]), 'scree'),
]
PALETTES = {
 'alpine': ('alpine_turf','alpine_snowfield','alpine_gravel'),
 'moor': ('meadow_grass','grey_heather_moor','packed_earth'),
 'upland': ('meadow_grass','alpine_turf','alpine_gravel'),
 'scree': ('alpine_turf','alpine_bedrock','alpine_gravel'),
}
VIEW_PREFIX = 'StreamView_'
HALF_WIDTH = 40.0
VIEW_DEPTH = 145.0


def region_specs(region):
    result=[]
    for identity,a,b,palette in LINKS:
        for here,there,sign in ((a,b,1),(b,a,-1)):
            if here[0] == region:
                result.append(dict(id=identity, portal=here[1], destination=there[0],
                    anchor=here[2], outward=here[3], uvSign=sign, palette=palette,
                    preloadDistance=170, retainDistance=220, blendDistance=65,
                    collarDepth=42, halfWidthTiles=3, viewHalfWidth=HALF_WIDTH,
                    viewDepth=VIEW_DEPTH, previewPrefix=VIEW_PREFIX+identity+'__',
                    overflowSuffix='_StreamOverflow_'+identity))
    return result


def materials_for(region):
    return {name for spec in region_specs(region) for name in PALETTES[spec['palette']]}


def clip_plane(mesh, edge, normal, limit=0.):
    """Exact half-space clip, preserving UVs, colour coverage and winding."""
    if not mesh.triangle_count: return mesh.copy()
    columns=[mesh.positions,mesh.normals,mesh.uvs]
    if mesh.colors is not None: columns.append(mesh.colors)
    values=np.concatenate(columns,axis=1)
    distances=(mesh.positions[:,[0,2]]-edge)@normal-limit
    faces=mesh.indices.reshape(-1,3)
    fd=distances[faces]
    keep=fd.max(axis=1)<=1e-9
    crossing=(fd.min(axis=1)<-1e-9)&~keep
    extra=[]
    for face in faces[crossing]:
        polygon=[]
        for j in range(3):
            a,b=int(face[j]),int(face[(j+1)%3]); da,db=distances[a],distances[b]
            if da<=0: polygon.append(values[a])
            if (da<0<db) or (db<0<da):
                polygon.append(values[a]+(values[b]-values[a])*(da/(da-db)))
        for j in range(1,len(polygon)-1): extra.extend((polygon[0],polygon[j],polygon[j+1]))
    kept=values[faces[keep]].reshape(-1,values.shape[1])
    if extra: kept=np.concatenate([kept,np.asarray(extra)])
    result=mesh.copy()
    result.positions,result.normals,result.uvs=kept[:,:3],kept[:,3:6],kept[:,6:8]
    if result.colors is not None: result.colors=kept[:,8:12]
    result.indices=np.arange(len(kept))
    return _compact(result)


def clip_rect(mesh, edge, forward, side, near, far, width=HALF_WIDTH):
    result=clip_plane(mesh,edge,forward,far)
    result=clip_plane(result,edge,-forward,-near)
    result=clip_plane(result,edge,side,width)
    return clip_plane(result,edge,-side,width)


def split_overflow(mesh, edge, forward, side):
    # Disjoint complement of the receiving strip. Unlike centroid clipping,
    # even a huge backdrop triangle has an exact edge with no missing sliver.
    behind=clip_plane(mesh,edge,forward)
    beyond=clip_plane(mesh,edge,-forward)
    left=clip_plane(beyond,edge,side,-HALF_WIDTH)
    right=clip_plane(beyond,edge,-side,-HALF_WIDTH)
    from amberwood.mesh import merge
    return merge([behind,left,right], material=mesh.material), clip_rect(mesh,edge,forward,side,0,100000)



def _refine_collar(mesh, edge, forward, side):
    """Keep the material edge below a metre instead of a repeated triangle saw."""
    columns = [mesh.positions, mesh.normals, mesh.uvs]
    if mesh.colors is not None: columns.append(mesh.colors)
    values = np.concatenate(columns, axis=1)
    faces = mesh.indices.reshape(-1, 3)
    for _ in range(3):
        triangles = values[faces, :3]
        centres = triangles.mean(axis=1)[:, [0, 2]] - edge
        depth, lateral = centres @ forward, centres @ side
        longest = np.maximum.reduce([np.linalg.norm(triangles[:, a] - triangles[:, b], axis=1)
                                     for a, b in ((0, 1), (1, 2), (2, 0))])
        selected = (depth > -16) & (depth < 5) & (abs(lateral) < 55) & (longest > .9)
        if not selected.any(): break
        old = faces[selected]
        mids = np.stack([(values[old[:, a]] + values[old[:, b]]) / 2
                         for a, b in ((0, 1), (1, 2), (2, 0))], axis=1)
        ids = np.arange(len(values), len(values) + 3 * len(old)).reshape(-1, 3)
        values = np.concatenate([values, mids.reshape(-1, values.shape[1])])
        a, b, c = old.T; ab, bc, ca = ids.T
        faces = np.concatenate([faces[~selected], np.stack([a, ab, ca], axis=1),
            np.stack([ab, b, bc], axis=1), np.stack([ca, bc, c], axis=1), np.stack([ab, bc, ca], axis=1)])
    mesh.positions, mesh.normals, mesh.uvs = values[:, :3], values[:, 3:6], values[:, 6:8]
    if mesh.colors is not None: mesh.colors = values[:, 8:12]
    mesh.indices = faces.reshape(-1)


def _apply_one(build, spec, peers):
    edge = np.array(spec['anchor'])[[0, 2]]
    forward = np.array(spec['outward'], float)
    side = np.array([-forward[1], forward[0]])
    level = spec['anchor'][1]

    def grade(points):
        points = points.copy()
        relative = points[:, [0, 2]] - edge
        depth, lateral = relative @ forward, relative @ side
        # One broad saddle, open across the road and rising into both shoulders.
        target = level + 8 * (1 - np.exp(-(lateral / 30)**2))
        blend = np.clip((depth + 42) / 32, 0, 1)
        blend = blend * blend * (3 - 2 * blend)
        shoulder = np.clip((abs(lateral) - HALF_WIDTH) / (68 - HALF_WIDTH), 0, 1)
        blend *= 1 - shoulder * shoulder * (3 - 2 * shoulder)
        # A nearby second road may blend its outer shoulder into this region,
        # but never change another road's surveyed receiving strip. Mirrorhold
        # has two north-facing cols only 87m apart. Fade protection outside the
        # 40m cut so the unsplit ground stays continuous between the cols.
        for peer in peers:
            if peer['id'] == spec['id']: continue
            pf=np.asarray(peer['outward'],float);ps=np.array([-pf[1],pf[0]])
            pr=points[:,[0,2]]-np.asarray(peer['anchor'])[[0,2]]
            pd,pl=pr@pf,pr@ps
            protection=np.clip((pd+42)/32,0,1)
            protection=protection*protection*(3-2*protection)
            outside=np.clip((abs(pl)-HALF_WIDTH)/3,0,1)
            outside=outside*outside*(3-2*outside)
            blend*=1-protection*(1-outside)
        points[:, 1] += (target - points[:, 1]) * blend
        return points

    for bucket in (build.terrain_meshes, build.water_meshes):
        for name, original in list(bucket.items()):
            if name.startswith(VIEW_PREFIX) or '_StreamOverflow_' in name:
                continue
            if name.startswith('Terrain_'):
                _refine_collar(original, edge, forward, side)
            original.positions = grade(original.positions)
            original.recompute_normals(180)
            # Both directions use the same gravel and UV frame for the last
            # few metres. A ragged inner edge blends back to each region's soil.
            if name.startswith('Terrain_'):
                faces = original.indices.reshape(-1, 3)
                coords = original.positions[:, [0, 2]] - edge
                depth, lateral = coords @ forward, coords @ side
                near = np.minimum(np.clip(.5 + (depth + 10 - 1.8 * np.sin(lateral * .19)
                                             - .7 * np.sin(lateral * .73)) / 1.2, 0, 1),
                                  np.clip((60 - abs(lateral)) / 3, 0, 1))
                if near.max(initial=0) > .5:
                    if original.colors is None: original.colors = np.ones((len(original.positions), 4))
                    alpha = original.colors[:, 3].copy()
                    u, v = lateral * spec['uvSign'], depth * spec['uvSign']
                    road = np.clip(.5 + (3.4 + .4 * np.sin(v * .3) - abs(u)) / 1.0, 0, 1)
                    frost = np.minimum(np.clip((abs(u) - 7) / 1.2, 0, 1),
                        np.clip(.5 + (np.sin(u * .17) + np.cos(v * .23) +
                            .45 * np.sin((u + v) * .37) - .35) / .8, 0, 1))
                    # Continuous substrate below the cutout paint prevents
                    # cracks where interpolated masks meet inside a triangle.
                    # Centimetre offsets avoid coplanar depth fighting.
                    for suffix, mask, material, lift in [
                            ('Turf', np.ones_like(road), PALETTES[spec['palette']][0] + '_ground', .008),
                            ('Frost', frost, PALETTES[spec['palette']][1] + '_ground', .016),
                            ('Road', road, PALETTES[spec['palette']][2] + '_ground', .024)]:
                        gravel = original.copy()
                        gravel.positions[:, 1] += lift
                        gravel.colors[:, 3] = np.minimum.reduce([alpha, near, mask])
                        gravel.indices = faces[gravel.colors[faces, 3].max(axis=1) >= .5].reshape(-1)
                        gravel.material = material
                        gravel.uvs = np.stack([u, v], axis=1) * .28
                        bucket[name + '_StreamCollar_' + spec['id'] + '_' + suffix] = _compact(gravel)
            bucket[name] = _compact(original)
        for name, original in list(bucket.items()):
            if not original.triangle_count or '_StreamOverflow_' in name: continue
            front,overflow=split_overflow(original,edge,forward,side)
            bucket[name]=_compact(front)
            if overflow.triangle_count: bucket[name+spec['overflowSuffix']]=_compact(overflow)
    kept = []
    lifted = {}
    for placement in build.placements:
        p = np.asarray(placement.position, float)
        relative = p[[0, 2]] - edge
        depth, lateral = relative @ forward, relative @ side
        if depth > -42 and abs(lateral) < 68:
            # The receiving scene supplies this side of the border. Removing
            # only perimeter dressing leaves services and landmarks unchanged.
            if (depth > 0 and abs(lateral) < HALF_WIDTH) or (abs(lateral) < 7 and placement.kind in ('tree', 'foliage', 'rock', 'undergrowth')):
                continue
            ground=p.copy();ground[1]=build.terrain.height_at(p[0],p[2])
            lift=float(grade(ground[None,:])[0,1]-ground[1])
            p[1]+=lift
            placement.position=tuple(p)
            lifted[placement.node]=lift
        kept.append(placement)
    build.placements[:] = kept
    landmark_nodes={entry.get('id'):entry.get('node') for entry in build.landmarks}
    def linked_node(entry):
        if entry.get('node'): return entry['node']
        if entry.get('landmark'): return landmark_nodes.get(entry['landmark'])
        if entry.get('secret'): return 'Secret_'+entry['secret'].replace('-','_')
        return None
    portal_nodes={entry.get('id'):linked_node(entry) for entry in build.portals}
    seen=set()
    for name in ('landmarks','interactives','npc_markers','harvestables','portals','spawns'):
        for entry in getattr(build,name,[]):
            # Some builders reuse one record in multiple collections. Move it
            # once, by its physical prop's delta, preserving authored offsets.
            if id(entry) in seen: continue
            seen.add(id(entry))
            node=linked_node(entry)
            if node is None and name=='spawns': node=portal_nodes.get(entry.get('id'))
            lift=lifted.get(node)
            if lift is not None and 'position' in entry:
                entry['position'][1]+=lift
    t=build.terrain
    points=np.stack([t.gx.ravel(),t.height.ravel(),t.gz.ravel()],axis=1)
    t.height=grade(points)[:,1].reshape(t.height.shape)


def apply(build, region):
    from copy import copy
    specs=region_specs(region)
    build.streaming_borders=specs
    build.vista_materials=getattr(build,'vista_materials',set())|materials_for(region)
    # All surveyed neighbours use their own real receiving scene.
    for bucket in (build.terrain_meshes,build.water_meshes):
        for name in list(bucket):
            if name.startswith('Backdrop_Neighbour'): del bucket[name]
    build.border_vistas=[]
    for spec in specs:
        _apply_one(build,spec,specs)
        anchor=np.asarray(spec['anchor'],float); forward=np.asarray(spec['outward'],float)
        # Source metadata and the server's trigger use the same tile centres.
        for portal in build.portals:
            if portal.get('id')==spec['portal']:
                p=anchor.copy();p[[0,2]]+=forward
                portal['position']=p.tolist()
                ox,oy={'amberwood':(116,116),'grey_moors':(116,116),
                       'amethyst_barrens':(116,116),'mirrorhold':(120,96),
                       'whitehorn_range':(120,120)}[region]
                portal['serverTile']=[int(np.floor(p[0]+ox)),int(np.floor(oy-p[2]))]
    # The resident root contains exact subsets of its authored geometry. Only
    # its matching approach is shown while neighbouring; full geometry becomes
    # active on adoption. This prevents other exits and distant cities leaking
    # through the region-local border frame.
    # Props remain whole shared instances: their pivots can sit outside a view
    # while a boulder or tree canopy crosses its edge. Cache all-part local
    # bounds once per mesh, then transform the eight corners once per placement.
    local_corners={}
    preview_candidates=[]
    for p in build.placements:
        if p.node.startswith(VIEW_PREFIX): continue
        if p.mesh not in local_corners:
            mesh=build.meshes.get(p.mesh)
            if mesh is None or not mesh.triangle_count:
                local_corners[p.mesh]=None
            else:
                low,high=mesh.bounds()
                local_corners[p.mesh]=np.array([
                    [x,y,z] for x in (low[0],high[0])
                    for y in (low[1],high[1]) for z in (low[2],high[2])])
        corners=local_corners[p.mesh]
        if corners is None: continue
        world=(corners*p.scale)@rotation_y(p.rotation_y)[:3,:3].T+np.asarray(p.position)
        preview_candidates.append((p,world[:,[0,2]]))
    for spec in specs:
        edge=np.asarray(spec['anchor'])[[0,2]];forward=np.asarray(spec['outward'],float)
        side=np.array([-forward[1],forward[0]])
        for bucket in (build.terrain_meshes,build.water_meshes):
            for name,mesh in list(bucket.items()):
                if name.startswith(VIEW_PREFIX) or '_StreamOverflow_' in name: continue
                part=clip_rect(mesh,edge,forward,side,-VIEW_DEPTH,0)
                if part.triangle_count: bucket[spec['previewPrefix']+name]=part
        for p,corners in preview_candidates:
            relative=corners-edge
            depth,lateral=relative@forward,relative@side
            if (depth.max()>=-VIEW_DEPTH and depth.min()<=0
                    and lateral.max()>=-HALF_WIDTH and lateral.min()<=HALF_WIDTH):
                duplicate=copy(p); duplicate.node=spec['previewPrefix']+p.node
                duplicate.collides=False;duplicate.extras=None
                build.placements.append(duplicate)
