"""Compose one complete continent, then export named territories and 96m cells.

Run regional content extraction first with build_library.py. All terrain,
water, roads and ecology are authored in the global world before partitioning.
The complete GLB is a reproducible review artifact, never a client dependency.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import inspect
import json
import math
from pathlib import Path
import pickle
import re
import shutil
import sys
import time
import numpy as np
from scipy.ndimage import label, distance_transform_edt

HERE=Path(__file__).resolve().parent
REGIONS=HERE.parent
MAPS=REGIONS.parent
CLIENT=MAPS.parents[1]
sys.path.insert(0,str(HERE))
import landscape as L
from world_layout import World,CELL,CHUNK
from content import Content,spawn_position
import scene_io as S
from terrain_export import partition_surface
from crossings import prepare_contracts,apply_manifest
from amberwood import gltf as G,mesh as M
from continent_geography import polygon_rectangles,clip_owned_mesh
from build_progress import Progress
SHAPING_SOURCES=('landscape.py','world_layout.py','content.py','assemblies.py','crown_support.py','westhaven_support.py','ferry_export.py','ferry_support.py','mirror_support.py','manymouth_support.py','mirror_streets.py','four_gates_support.py','amberwood_support.py','amberwood_access.py','mirror_lake_support.py','ssarathi_bank_support.py','manymouth_boats.py','terrain_export.py','scene_io.py','grey_crossings.py','four_gates_sage.py','door_approaches.py','hull_settle.py','resource_trails.py','object_edits.py')


EMPTY_SHA256=hashlib.sha256(b'').hexdigest()


def object_edits_digest():
    # An absent continent-edits.json is the empty edit set, as for every earlier composition.
    path=HERE/'continent-edits.json'
    return digest(path) if path.exists() else EMPTY_SHA256
# Reporting only: the command line attaches this to the output directory.
PROGRESS=Progress(None)


def package(region):return MAPS/'four-gates' if region=='four_gates' else REGIONS/region

def json_write(path,data):
    def clean(value):
        if isinstance(value,np.ndarray):return value.tolist()
        if isinstance(value,np.generic):return value.item()
        if isinstance(value,set):return sorted(value)
        raise TypeError(type(value).__name__)
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(path).write_text(json.dumps(data,indent=2,default=clean,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def composition_algorithm_sha():
    """Digest of the composition algorithm recorded in composition.json."""
    return hashlib.sha256((inspect.getsource(prepare)+inspect.getsource(ferry_landing)).encode()).hexdigest()


def ferry_landing(world,region,toward):
    index=world.ids.index(region);center=world.hub(region)
    inside=np.pad(world.owner==index,((0,1),(0,1)),mode='edge')
    sea_labels,_=label(world.water['sea_mask'],structure=np.ones((3,3)))
    ocean_ids=np.unique(np.r_[sea_labels[0],sea_labels[-1],sea_labels[:,0],sea_labels[:,-1]])
    ocean=np.isin(sea_labels,ocean_ids[ocean_ids>0])
    shore_distance=distance_transform_edt(~ocean)*CELL
    excluded=getattr(world,'ferry_exclusion',np.zeros_like(world.obstacles))
    coast=(world.height>.6)&(world.height<3.5)&(shore_distance<=12)&inside&~world.obstacles&~excluded
    for quay in world.quay_contacts:
        coast&=np.hypot(world.gx-quay['center'][0],world.gz-quay['center'][1])>=20.
    z,x=np.nonzero(coast)
    if not len(x):raise ValueError(f'{region}: no coast for ferry landing')
    points=np.c_[world.x[x],world.z[z]]
    score=np.linalg.norm(points-center,axis=1)+.28*np.linalg.norm(points-np.array(toward),axis=1)
    from ferry_export import fit_landing
    from ferry_support import restore_selected_shores
    attempted=[];errors=[];original_height=world.height;contact_count=len(world.quay_contacts)
    for candidate in np.argsort(score,kind='stable'):
        point=points[candidate]
        if any(np.linalg.norm(point-prior)<6 for prior in attempted):continue
        attempted.append(point)
        world.height=original_height.copy()
        try:
            world.prepare_quay_court(point)
            restore_selected_shores(world)
            fit=fit_landing(world,point,region)
            if not hasattr(world,'ferry_selection'):world.ferry_selection=[]
            world.ferry_selection.append({'region':region,'position':point.tolist(),'candidatesTried':len(attempted),
                'mooringDepth':fit['minimumBoatDepth'],'contactError':fit['contactError']})
            return point
        except ValueError as error:errors.append(str(error))
        finally:
            world.height=original_height
            del world.quay_contacts[contact_count:]
        if len(attempted)>=64:break
    raise ValueError(f'{region}: none of {len(attempted)} ranked shoreline sites fits an actual quay and mooring; last failures: {errors[-3:]}')


def prepare(library,output):
    PROGRESS.start('compose',4);PROGRESS.step('loading libraries and content',0,4)
    plan_sha=digest(HERE/'diagonal-plan.json')
    edits_sha=object_edits_digest()
    profile_sha=digest(HERE/'legacy-server-profile/config/eloria/maps.txt')
    algorithm_sha=composition_algorithm_sha()
    sources={str(p.relative_to(CLIENT)):digest(p) for p in HERE.glob('*.py')}
    shaping={name:sources[str((HERE/name).relative_to(CLIENT))] for name in SHAPING_SOURCES}
    templates=json.loads((HERE/'legacy-contracts.json').read_text())
    legacy=json.loads((HERE/'legacy-geography.json').read_text())
    started=time.monotonic();world=World()
    print(f'Global landform sampled in {time.monotonic()-started:.1f}s',flush=True)
    content=Content(world,library,templates,legacy);content.load()
    PROGRESS.step('roads and routing',1,4)
    from amberwood_access import prepare_amberwood_access,refresh_amberwood_access_heights
    from amberwood_support import prepare_amberwood_routes,apply_amberwood_support
    prepare_amberwood_access(world,content)
    from grey_crossings import prepare_grey_crossings,refresh_grey_crossing_heights
    prepare_grey_crossings(world,content)
    from four_gates_sage import prepare_four_gates_sage,refresh_four_gates_sage_heights
    prepare_four_gates_sage(world,content)
    from door_approaches import prepare_door_approaches,door_road_end,door_road_end_near,server_road_end,door_road_waypoints,SERVER_ROAD_END_LEG_METRES
    prepare_door_approaches(world,content)
    from crown_support import apply_crown_support
    from westhaven_support import apply_westhaven_support
    from manymouth_support import apply_manymouth_support
    from mirror_streets import apply_mirror_street_footings,add_mirror_streets,apply_mirror_access
    apply_crown_support(world,content)
    apply_westhaven_support(world,content)
    apply_manymouth_support(world,content)
    apply_mirror_street_footings(world,content)
    world.settle_foundations()
    from mirror_lake_support import prepare_mirror_lake_support,finish_mirror_lake_support
    prepare_mirror_lake_support(world,content)
    # Every prepare stage that moves retained content has run: the router
    # sees each structure where it finally stands.
    world.registered_obstacles=content.register_obstacles()
    world.plan_connections()
    add_mirror_streets(world,content)
    from ferry_export import fit_landing
    from ferry_support import remember_ferry_fit,restore_selected_shores,validate_final_ferries
    for link in world.connections:
        if link['type']=='walk':
            anchor=np.array(link['anchor']);normal=np.array(link['normal'])
            for side,region in enumerate(link['regions']):
                outward=normal if side==0 else -normal
                hub=world.hub(region)
                terminal=anchor-outward*9
                # A seam terminal stands on open ground by construction (the crossing
                # choice charges terminals inside solids), so the road's own solids are
                # the hub's only: its last stretch threads a city wall's gate instead of
                # crossing the wall its terminal stands beside (measured at Four Gates
                # with the terrain terms on: 31 m through City_Wall_44 and _45, and the
                # seam's crossing and return records unreachable).
                path=world.route(hub,terminal,region=region,own=world.solids_at_ends(hub))
                path=np.vstack([path,anchor-outward*4,anchor,anchor+outward*4])
                world.add_road(path,width=4,name=link['id']+'-'+region)
                print(f'Road {region} to {link["id"]}: {len(path)} stations',flush=True)
        else:
            ends=[]
            for side,region in enumerate(link['regions']):
                other=link['regions'][1-side]
                landing=ferry_landing(world,region,world.regions[other]['center'])
                world.prepare_quay_court(landing)
                restore_selected_shores(world)
                remember_ferry_fit(world,fit_landing(world,landing,region))
                hub=world.hub(region)
                world.add_road(world.route(hub,landing,region=region),width=2.5,name=link['id']+'-'+region)
                ends.append(landing.tolist())
            link['landings']=ends
    # Inhabited approaches grow from the public roads to existing doorways.
    # Close destinations share a trail; resources remain in the wilderness.
    for region in world.ids:
        hub=world.hub(region)
        seen=[]
        for entry in content.templates[region].get('portals',[]):
            target=entry.get('targetMap',entry.get('destinationMap',''))
            if target in world.ids or 'position' not in entry:continue
            point=content.mapped_point(region,entry['position'],entry.get('node',entry.get('doorNode')),entry.get('landmark'))[[0,2]]
            if int(world.owner_at(*point))!=world.ids.index(region):continue
            if any(np.linalg.norm(point-p)<7 for p in seen):continue
            seen.append(point)
            # A door inside a retained pavilion gets its road on the pavilion's open side;
            # a designed climb is routed through its authored waypoints in legs.
            legs=[hub]+door_road_waypoints(content,region,entry.get('id'))+[door_road_end(content,region,entry.get('id'),point)]
            path=np.vstack([world.route(a,b,region=region)[:-1 if index<len(legs)-2 else None] for index,(a,b) in enumerate(zip(legs,legs[1:]))])
            world.add_road(path,width=1.65,name='door-'+region+'-'+str(entry.get('id','entry')))
    # The server also declares hidden rooms and instance returns that are not
    # client portal markers. Give these discoveries narrow branches from the
    # nearest public route, using the same authored point transform as export.
    profile=HERE/'legacy-server-profile/config/eloria/maps.txt'
    destinations={region:[] for region in world.ids}
    for number,line in enumerate(profile.read_text(encoding='utf-8').splitlines(),1):
        fields=[part.strip() for part in line.split('#',1)[0].split('|')]
        if not fields or fields[0]!='portal' or len(fields) not in (7,8):continue
        start=2 if len(fields)==7 else 3
        source,target=fields[1],fields[start+2]
        if source in world.ids and target in world.ids:continue
        for region,tile in ((source,fields[start:start+2]),(target,fields[start+3:start+5])):
            if region not in world.ids:continue
            point=content.mapped_server_point(region,list(map(int,tile)))[[0,2]]
            if int(world.owner_at(*point))==world.ids.index(region):destinations[region].append((number,point,source,target))
    for region,entries in destinations.items():
        seen=[]
        for number,point,source,target in entries:
            if any(np.linalg.norm(point-p)<5 for p in seen):continue
            seen.append(point)
            # A server portal with its own pin is routed to that dry ground from
            # the network on that side of the portal and runs straight on to the
            # portal (a deck over water); one beside a pinned door shares the
            # door's road end.
            pin=server_road_end(content,region,point,source,target)
            end=pin if pin is not None else door_road_end_near(content,region,point)
            candidates=np.vstack([np.asarray(road['points'])[:,[0,2]] for road in world.roads])
            candidates=candidates[world.owner_at(candidates[:,0],candidates[:,1])==world.ids.index(region)]
            if pin is not None:
                side=(candidates-point)@(end-point)>0
                if side.any():candidates=candidates[side]
            distances=np.linalg.norm(candidates-end,axis=1)
            nearest=int(np.argmin(distances))
            if distances[nearest]<4 and pin is None:continue
            path=world.route(candidates[nearest],end,region=region)
            if pin is not None and np.linalg.norm(pin-point)>SERVER_ROAD_END_LEG_METRES:path=np.vstack([path,point])
            world.add_road(path,width=1.65,name=f'discovery-{region}-{number}')
    # Authored resource sites on steep ground that no corridor serves get a trail.
    from resource_trails import prepare_resource_trails
    trails=prepare_resource_trails(world,content,HERE/'legacy-server-profile/config/eloria')
    print(f"Resource trails: {len(trails['trails'])} for {trails['steepSites']} steep sites ({trails['servedSites']} already beside a road)",flush=True)
    prepare_amberwood_routes(world,content)
    # Every alignment exists now: record the retained solids any road still crosses.
    world.road_solid_crossings=world.solid_crossings(content.solid_boxes())
    print(f'Roads through retained solids: {len(world.road_solid_crossings)} (solid fallbacks {len(world.routing_report()["solidFallbacks"])})',flush=True)
    world.settle_roads()
    PROGRESS.step('supports and ground',2,4)
    from mirror_support import apply_mirror_support
    from four_gates_support import apply_four_gates_support
    apply_four_gates_support(world,content)
    apply_mirror_support(world,content)
    apply_mirror_access(world,content)
    apply_amberwood_support(world,content)
    from ssarathi_bank_support import apply_ssarathi_banks
    apply_ssarathi_banks(world,content)
    finish_mirror_lake_support(world,content)
    world.water=L.water_fields(world.gx,world.gz,height=world.height,plan=world.plan)
    final_ferries=validate_final_ferries(world)
    print(f'Final ferry shore readback: {len(final_ferries["finalFits"])} complete quay/mooring fits',flush=True)
    content.reground()
    from manymouth_boats import apply_manymouth_boats
    apply_manymouth_boats(world,content)
    from hull_settle import apply_hull_settle
    apply_hull_settle(world,content)
    refresh_amberwood_access_heights(world,content)
    refresh_grey_crossing_heights(world,content)
    refresh_four_gates_sage_heights(world,content)
    content.ecological_scatter()
    if any(digest(HERE/name)!=sha for name,sha in shaping.items()):
        raise ValueError('Landscape shaping source changed during composition; run prepare again')
    if digest(HERE/'diagonal-plan.json')!=plan_sha:raise ValueError('Landscape plan changed during composition')
    if object_edits_digest()!=edits_sha:raise ValueError('Object edits changed during composition')
    if digest(profile)!=profile_sha:raise ValueError('Authored entrances changed during composition')
    PROGRESS.step('writing the composition',3,4)
    # Cache is local generated state with exact source certificates. Never load
    # an arbitrary downloaded pickle as an authored continent.
    with (output/'composed.pkl').open('wb') as handle:pickle.dump((world,content),handle,protocol=5)
    json_write(output/'composition.json',{'schema':1,'planSha256':plan_sha,'objectEditsSha256':edits_sha,'objectEdits':{'document':content.edits.doc,'report':content.edits.report},'entranceProfileSha256':profile_sha,'compositionAlgorithmSha256':algorithm_sha,
        'library':{r:digest(Path(library)/r/'source-certificate.json') for r in world.ids},
        'sources':sources,
        'objects':len(content.objects),'roads':len(world.roads),'assemblies':content.assembly_records,
        'mirrorLakeSupport':world.mirror_lake_support,'ssarathiBankSupport':world.ssarathi_bank_support,
        'manymouthBoats':world.manymouth_boats,'greyCrossings':world.grey_crossings,'fourGatesSage':world.four_gates_sage,
        'doorApproaches':world.door_approaches,'hullSettle':world.hull_settle,'roadGradingPasses':world.road_grading_passes,'resourceTrails':world.resource_trails,
        'routing':{**world.routing_report(),'solidCrossings':world.road_solid_crossings},
        'elapsedSeconds':round(time.monotonic()-started,2)})
    PROGRESS.step('composition written',4,4)
    return world,content


def load_composed(output,library):
    certificate=json.loads((output/'composition.json').read_text())
    if certificate['planSha256']!=digest(HERE/'diagonal-plan.json'):raise ValueError('Landscape plan changed; recompose before export')
    if certificate.get('objectEditsSha256',EMPTY_SHA256)!=object_edits_digest():raise ValueError('Object edits changed; recompose before export')
    if certificate.get('entranceProfileSha256')!=digest(HERE/'legacy-server-profile/config/eloria/maps.txt'):raise ValueError('Authored entrance profile changed; recompose before export')
    algorithm_sha=composition_algorithm_sha()
    if certificate.get('compositionAlgorithmSha256')!=algorithm_sha:raise ValueError('Composition algorithm changed; recompose before export')
    for region,sha in certificate['library'].items():
        if sha!=digest(Path(library)/region/'source-certificate.json'):raise ValueError(f'{region}: source content changed; recompose')
    for relative,sha in certificate['sources'].items():
        # Export-only fixes may reuse the completed landform. Its shaping
        # modules and source content are the exact terrain authority.
        if Path(relative).name in SHAPING_SOURCES and digest(CLIENT/relative)!=sha:
            raise ValueError(f'{relative}: landscape composition changed; recompose')
    with (output/'composed.pkl').open('rb') as handle:return pickle.load(handle)


def bridge_scene(world,path):
    from bridge_export import build_bridges
    return build_bridges(world,path)


def local_point(point,center):
    p=np.array(point,float).copy();p[[0,2]]-=center;return p.tolist()


def manifest_for(world,content,region):
    m=copy.deepcopy(content.templates[region]);center=np.array(world.regions[region]['center']);origin,cells=world.address(region)
    hub=world.hub(region);arrival=local_point([hub[0],float(world.height_at(*hub)),hub[1]],center)
    def transform(item):
        if isinstance(item,list):return [transform(v) for v in item]
        if not isinstance(item,dict):return item
        result={k:transform(v) for k,v in item.items()}
        node=item.get('node',item.get('doorNode'));landmark=item.get('landmark')
        for key in ('position','arrivalPosition','targetPosition','center'):
            v=item.get(key)
            if isinstance(v,list) and len(v)==3 and all(isinstance(a,(float,int)) for a in v):
                result[key]=local_point(content.mapped_point(region,v,node,landmark),center)
        if 'serverTile' in item:
            if 'position' in result: p=result['position']
            else:
                old_origin=content.templates[region]['coordinateTransform']['serverOrigin']
                p=local_point(content.mapped_point(region,[item['serverTile'][0]-old_origin[0]+.5,0,old_origin[1]-item['serverTile'][1]-.5]),center)
            result['serverTile']=[math.floor(p[0]+origin[0]),math.floor(origin[1]-p[2])]
        return result
    for key in ('landmarks','interactives','portals','spawnPoints','pointsOfInterest','harvestables','npcMarkers','creatureSpawns','spawns','effects','ambientPopulation','lighting','environment'):
        if key in m:m[key]=transform(m[key])
    obsolete_landmarks={'whitehorn_range':('Landmark_rope_bridge_',),'amberwood':('Landmark_Survey_ridge-bridge',)}
    if region in obsolete_landmarks:
        # These wilderness spans were replaced by the continental road bridges.
        # Named-location UI reads landmark coordinates without checking nodes.
        m['landmarks']=[p for p in m.get('landmarks',[]) if not str(p.get('node','')).startswith(obsolete_landmarks[region])]
    m['portals']=[p for p in m.get('portals',[]) if p.get('destinationMap',p.get('targetMap')) not in world.ids]
    m['streamingBorders']=[]
    for old in ('authoredGeometry','landscapeRevision','runtimePopulation','contentLayout','water','roads','paths','gates','bridges','districts','regions',
                'borderVistas','lodGroups','lensVaultApproach','secretApproaches','compactLandscape','terraces','buildNotes','assumptions','statistics'):
        m.pop(old,None)
    lo,hi=world.bounds(region);h=world.height
    minimum=[float(lo[0]-center[0]),float(h.min()),float(lo[1]-center[1])]
    maximum=[float(hi[0]-center[0]),float(h.max()+50),float(hi[1]-center[1])]
    m['asset'].update(id=region,glb='world.glb',units='meters',bounds={'min':minimum,'max':maximum})
    m['asset']['mapBounds']={'min':minimum,'max':maximum}
    m['asset']['playableBounds']={'min':minimum,'max':maximum}
    m['bounds']={'min':minimum,'max':maximum}
    m['coordinateTransform']={'metresPerTile':1.,'serverOrigin':origin,'serverCells':cells,'origin':[0,0,0],
        'walkingHeight':arrival[1],'invertServerY':True,
        'addressableWorldBounds':{'min':[-origin[0],origin[1]-cells[1]],'max':[cells[0]-origin[0],origin[1]]}}
    m['navigation']={'surfaceNodePrefixes':['Terrain_','Walk_'],'terrainConforming':True,'authority':'server',
                     'defaultSpawn':'continent-arrival','collisionFile':'collision.bin'}
    m['spawnPoints']=[{'id':'continent-arrival','default':True,'position':arrival,'facing':[0,0,-1]}]
    solid=[o['node'] for o in content.objects if o['region']==region and o.get('collides')]
    m['collision']={'file':'collision.bin','binary':'collision.bin','format':'EWCG','formatVersion':2,'version':2,
                    'cellMetres':.5,'cellSize':.5,'authoredSurfaceExport':True,'gridAlignment':'tile-centres-v1','nodeNames':solid}
    m['minimap']={'file':'minimap.webp','image':'minimap.webp','bounds':m['bounds'],'northUp':True,
        'worldMin':[minimum[0],minimum[2]],'worldMax':[maximum[0],maximum[2]],
        'imageSize':[int(round(maximum[0]-minimum[0])),int(round(maximum[2]-minimum[2]))],'pixelsPerMetre':1}
    m['continentGeography']={'revision':'diagonal-spine-v1','translation':[float(center[0]),0,float(center[1])],
                            'ownershipPolygon':world.polygons[region],'geometryMode':'continent-chunks-v1'}
    m['terrainRevision']='diagonal-spine-v1'
    m['sources']=['_continent/diagonal-plan.json','_continent/build_continent.py','_continent/build_library.py']
    m['knownLimitations']=[]
    apply_manifest(world,region,m)
    # One physically consistent light, sea and haze across the whole landmass.
    env=m.setdefault('environment',{})
    env['sun']={'direction':[-.45,-.78,-.43],'color':[1.,.94,.83],'energy':1.1}
    env['ambient']={'color':[.60,.67,.72],'energy':.6}
    return m


def add_to_exporter(exporter,world,content,region,terrain_doc,terrain_body,terrain_roots,objects,bridge_doc,bridge_body,bridges,global_space=False):
    center=np.array(world.regions[region]['center'])
    offset=np.zeros(3) if global_space else np.array([-center[0],0,-center[1]])
    if terrain_roots:exporter.add(terrain_doc,terrain_body,terrain_roots,transforms={r:offset for r in terrain_roots})
    for obj in objects:
        source=obj.get('libraryRegion',region);doc,body=content.documents[source]
        roots=obj.get('indices',[obj['index']])
        exporter.add(doc,body,roots,transforms={index:obj['shift']+offset for index in roots},prefix=region+'_',node_prefix=obj.get('nodePrefix',''))
    for bridge in bridges:
        exporter.add(bridge_doc,bridge_body,bridge['roots'],transforms={r:offset for r in bridge['roots']},prefix=region+'_')


def prune_retired_exports(manifests):
    """Remove only identifiable generated cells after the new export succeeds."""
    for region,manifest in manifests.items():
        root=(package(region)/'chunks').resolve()
        keep={row['id'] for row in manifest['streamingChunks']['chunks']}
        for directory in root.iterdir():
            if not directory.is_dir() or directory.name in keep or not re.fullmatch(r'\d+_\d+',directory.name):continue
            resolved=directory.resolve()
            resolved.relative_to(root)
            old=resolved/'world.json'
            if not old.is_file():continue
            prior=json.loads(old.read_text(encoding='utf-8'))
            if prior.get('asset',{}).get('id')!=region+'__chunk_'+directory.name:continue
            if prior.get('continentGeography',{}).get('geometryMode')!='continent-chunks-v1':continue
            shutil.rmtree(resolved)
    shared=(HERE/'shared-assets').resolve()
    keep={Path(uri).name for manifest in manifests.values() for uri in manifest['externalResources']}
    for path in shared.iterdir():
        if path.is_file() and re.fullmatch(r'[0-9a-f]{64}\.(png|jpg)',path.name) and path.name not in keep:
            path.resolve().relative_to(shared);path.unlink()


def export_geometry(world,content,output):
    PROGRESS.start('geometry',len(world.ids))
    composition_sha=digest(output/'composition.json')
    export_sources={name:digest(HERE/name) for name in ('build_continent.py','scene_io.py','terrain_export.py','bridge_export.py','ferry_export.py','crossings.py','amberwood_access.py','manymouth_access.py','manymouth_village_streets.py','collision_export.py','mirror_access_geometry.py','grey_crossings.py')}
    prepare_contracts(world)
    terrain_path=output/'shared-terrain.glb';bridge_path=output/'bridges.glb'
    from ferry_export import build_ferries
    from amberwood_access import build_amberwood_access
    from manymouth_access import build_manymouth_access
    from mirror_access_geometry import build_mirror_access
    from grey_crossings import remap_grey_crossing_landmarks
    river_path=output/'river-bridges.glb';ferry_path=output/'ferry-quays.glb'
    access_path=output/'amberwood-access.glb'
    access_parts=build_amberwood_access(world,content,access_path)
    fishing_path=output/'manymouth-access.glb'
    fishing_parts=build_manymouth_access(world,content,fishing_path)
    mirror_path=output/'mirror-bank-access.glb'
    mirror_parts=build_mirror_access(world,content,mirror_path)
    river_parts=bridge_scene(world,river_path)
    ferry_parts=build_ferries(world,ferry_path)
    structures=S.Exporter(bridge_path);bridge_parts=[];structure_sources=[]
    for path,parts in ((river_path,river_parts),(ferry_path,ferry_parts),(access_path,access_parts),(fishing_path,fishing_parts),(mirror_path,mirror_parts)):
        doc,body=S.GR.load(path);structure_sources.append((doc,body))
        for part in parts:
            start=len(structures.doc['scenes'][0]['nodes'])
            structures.add(doc,body,part['roots'])
            bridge_parts.append(dict(part,roots=structures.doc['scenes'][0]['nodes'][start:].copy()))
    structures.write()
    json_write(output/'crossing-structures.json',{'bridges':world.bridge_report,'ferries':world.ferry_report,'amberwoodAccess':world.amberwood_access,'manymouthAccess':world.manymouth_access,'mirrorBankAccess':world.mirror_bank_access,'mirrorBankOpening':world.mirror_bank_opening})
    partitions=partition_surface(world,terrain_path)
    terrain_doc,terrain_body=S.GR.load(terrain_path);bridge_doc,bridge_body=S.GR.load(bridge_path)
    master_path=output/'continent.glb';master=S.Exporter(master_path)
    by_region={r:[o for o in content.objects if o['region']==r] for r in world.ids}
    by_bridge={r:[b for b in bridge_parts if b['region']==r] for r in world.ids}
    for region in world.ids:
        roots=[n for c in partitions[region].values() for n in c['roots']]
        add_to_exporter(master,world,content,region,terrain_doc,terrain_body,roots,by_region[region],bridge_doc,bridge_body,by_bridge[region],True)
    master_stats=master.write();master_sha=digest(master_path)
    json_write(output/'master-scene.json',dict(master_stats,sha256=master_sha,regions=world.ids))
    del master
    manifests={};grey_landmarks=[]
    for region in world.ids:
        root=package(region);shared=HERE/'shared-assets';center=np.array(world.regions[region]['center'])
        manifest=manifest_for(world,content,region)
        objects=by_region[region];bridges=by_bridge[region]
        manifest['collision']['nodeNames'].extend(part['node'] for part in bridges if part.get('collides'))
        # Retired Grey survey spans keep their generic identities on the actual emitted crossing floors.
        grey_landmarks+=remap_grey_crossing_landmarks(world,content,region,manifest,bridge_doc,bridge_body,bridges)
        chunks=partitions[region]
        for obj in objects:
            midpoint=(obj['low']+obj['high'])*.5
            cx=int((midpoint[0]-world.x0)//CHUNK);cz=int((midpoint[2]-world.z0)//CHUNK)
            name=f'{cx:02d}_{cz:02d}'
            entry=chunks.setdefault(name,{'roots':[],'bounds':[obj['low'].copy(),obj['high'].copy()],'cell':[cx,cz],'terrainCells':0})
            entry.setdefault('objects',[]).append(obj)
            entry['bounds']=[np.minimum(entry['bounds'][0],obj['low']),np.maximum(entry['bounds'][1],obj['high'])]
        for bridge in bridges:
            lo,hi=bridge['bounds'];mid=(lo+hi)*.5;cx=int((mid[0]-world.x0)//CHUNK);cz=int((mid[2]-world.z0)//CHUNK);name=f'{cx:02d}_{cz:02d}'
            entry=chunks.setdefault(name,{'roots':[],'bounds':[lo.copy(),hi.copy()],'cell':[cx,cz],'terrainCells':0})
            entry.setdefault('bridges',[]).append(bridge)
            entry['bounds']=[np.minimum(entry['bounds'][0],lo),np.maximum(entry['bounds'][1],hi)]
        exporter=S.Exporter(root/'world.glb',shared)
        add_to_exporter(exporter,world,content,region,terrain_doc,terrain_body,[r for c in chunks.values() for r in c['roots']],objects,bridge_doc,bridge_body,bridges)
        stats=exporter.write();manifest['performance']=stats;manifest['externalResources']=stats['externalResources']
        manifest['singleContinentSource']={'revision':'diagonal-spine-v1','masterSha256':master_sha,'planSha256':digest(HERE/'diagonal-plan.json')}
        manifest['streamingChunks']={'schemaVersion':'1.0','coordinateSpace':'territory-local','preloadDistance':240,'retainDistance':320,
            'maximumLoadedChunks':64,'maximumResidentBytes':268435456,'chunks':[]}
        for name,entry in sorted(chunks.items()):
            chunk_root=root/'chunks'/name;chunk=S.Exporter(chunk_root/'world.glb',shared)
            add_to_exporter(chunk,world,content,region,terrain_doc,terrain_body,entry['roots'],entry.get('objects',[]),bridge_doc,bridge_body,entry.get('bridges',[]))
            chunk_stats=chunk.write()
            c=copy.deepcopy(manifest)
            for key in ('streamingChunks','landmarks','interactives','portals','spawnPoints','pointsOfInterest','harvestables','npcMarkers','creatureSpawns','spawns','effects','interiors'):
                c.pop(key,None)
            bounds={'min':local_point(entry['bounds'][0],center),'max':local_point(entry['bounds'][1],center)}
            c['asset'].update(id=region+'__chunk_'+name,glb='world.glb',bounds=bounds)
            c['bounds']=bounds
            names={n.get('name') for n in chunk.doc['nodes']}
            c['collision']['nodeNames']=[n for n in manifest['collision']['nodeNames'] if n in names]
            c['collision'].pop('file',None);c['collision'].pop('binary',None)
            c['navigation'].pop('collisionFile',None)
            c['performance']=chunk_stats;c['externalResources']=chunk_stats['externalResources']
            json_write(chunk_root/'world.json',c)
            # Conservative geometry + BVH + texture allowance. Runtime has an
            # independent shared-texture pool; this deliberately overestimates.
            geometry_bytes=chunk_stats['glbBytes']*5
            shared_bytes=chunk_stats['sharedResourceResidentBytes']
            estimated=geometry_bytes+sum(shared_bytes.values())
            manifest['streamingChunks']['chunks'].append({'id':name,'manifest':f'chunks/{name}/world.json','bounds':bounds,
                'estimatedResidentBytes':estimated,'glbBytes':chunk_stats['glbBytes'],
                'geometryResidentBytes':geometry_bytes,'sharedResourceResidentBytes':shared_bytes})
        json_write(root/'world.json',manifest);manifests[region]=manifest
        print(f'{region}: exported {len(chunks)} independent chunks from the shared master',flush=True)
        PROGRESS.step(region,world.ids.index(region)+1,len(world.ids))
    prune_retired_exports(manifests)
    if any(digest(HERE/name)!=sha for name,sha in export_sources.items()):
        raise ValueError('Geometry export source changed during the build; export again before publication')
    if digest(output/'composition.json')!=composition_sha:raise ValueError('Composition changed during geometry export')
    json_write(output/'export.json',{'masterPath':str(master_path),'masterSha256':master_sha,
        'geometrySources':export_sources,'compositionSha256':composition_sha,'greyCrossingLandmarks':grey_landmarks,
        'regions':{r:{'world':str(package(r)/'world.json'),'glbSha256':digest(package(r)/'world.glb'),'chunks':len(m['streamingChunks']['chunks'])} for r,m in manifests.items()}})
    return manifests


def verify_geometry_export(output):
    """Reject a newer landform paired with an older or partially written GLB."""
    ledger=json.loads((output/'export.json').read_text(encoding='utf-8'))
    if ledger.get('compositionSha256')!=digest(output/'composition.json'):
        raise ValueError('Geometry does not match the composed landform; run the geometry stage before contracts')
    required={'build_continent.py','scene_io.py','terrain_export.py','bridge_export.py','ferry_export.py','crossings.py','amberwood_access.py','manymouth_access.py','manymouth_village_streets.py','collision_export.py','mirror_access_geometry.py','grey_crossings.py'}
    if set(ledger.get('geometrySources',{}))!=required:raise ValueError('Geometry export is missing its source certificate')
    for name,expected in ledger['geometrySources'].items():
        if digest(HERE/name)!=expected:raise ValueError(f'{name}: geometry export source changed; export again')
    if digest(output/'continent.glb')!=ledger['masterSha256']:raise ValueError('Exported master bytes changed')
    for region,entry in ledger['regions'].items():
        if digest(package(region)/'world.glb')!=entry['glbSha256']:raise ValueError(f'{region}: named geometry differs from its master export')
    return ledger


# Regional recipes still build their legacy march-border materials from the
# published geography, keyed by a per-crossing palette. Continent crossings are
# graded roads and decks, so the palette is the retained one where the same
# territory pair existed before and the first territory's biome otherwise.
REGION_PALETTES={'whitehorn_range':'alpine','grey_moors':'moor','amberwood':'upland','amethyst_barrens':'scree',
    'mirrorhold':'upland','sunmane_steppe':'steppe','four_gates':'pasture','westhaven':'pasture',
    'manymouth_delta':'pasture','crownwater':'causeway','verdant_stair':'upland','ssarathi_ruins':'moor'}


def crossing_palette(regions,legacy_connections):
    pair={str(r) for r in regions}
    for connection in legacy_connections:
        if {str(end.get('region')) for end in connection.get('ends',[])}==pair and connection.get('palette'):
            return str(connection['palette'])
    return REGION_PALETTES.get(str(regions[0]),'pasture')


def publish_geography(world,manifests,output):
    geography={'schema':1,'revision':'diagonal-spine-v1','axes':{'x':'east','y':'up','z':'south'},
        'units':'metres','worldWaterLevel':0,'geometryMode':'continent-chunks-v1','ownershipRasterMetres':CELL,
        'note':'One globally authored terrain, drainage, roads and settlements, then exact named ownership and 96m streaming chunks. Rebuild with _continent/build_continent.py; legacy geographic border synthesis is retired.',
        'masterSource':'_continent/generated/continent.glb','planSource':'_continent/diagonal-plan.json','regions':{},'connections':[]}
    for region,m in manifests.items():
        lo,hi=world.bounds(region);center=world.centers[world.ids.index(region)];origin,cells=world.address(region)
        local_lo=(lo-center).tolist();local_hi=(hi-center).tolist()
        protected=[]
        for key in ('landmarks','portals','spawnPoints'):
            for entry in m.get(key,[]):
                if isinstance(entry.get('position'),list):protected.append({'id':entry.get('id',entry.get('node','point')),'kind':key,'position':entry['position'],'radius':entry.get('radius',3)})
        geography['regions'][region]={'nativeManifestSource':str((package(region)/'world.json').relative_to(CLIENT)).replace('\\','/'),
            'nativeManifestSha256':digest(package(region)/'world.json'),'translation':[float(center[0]),0,float(center[1])],'rotationDegrees':0,
            'nativeServerOrigin':origin,'nativeServerCells':cells,'nativePlayableBounds':[local_lo,local_hi],
            'coreBounds':[lo.tolist(),hi.tolist()],'protectedDestinations':protected,
            'ownershipPolygon':world.polygons[region],'serverBounds':[[-origin[0],origin[1]-cells[1]],[cells[0]-origin[0],origin[1]]],
            'serverOrigin':origin,'serverCells':cells,'serverTileShift':[0,0],'atlasLabel':center.tolist()}
    legacy_connections=json.loads((HERE/'legacy-geography.json').read_text(encoding='utf-8')).get('connections',[])
    for connection in world.publication_connections:
        if connection['type']!='walk':continue
        frame=connection['ends'][0]['frame']
        geography['connections'].append({'id':connection['id'],'globalAnchor':frame['globalAnchor'],'normal':frame['outward'],
            'profile':'land','palette':crossing_palette([e['region'] for e in connection['ends']],legacy_connections),
            'roadWidth':8,'collarDepth':2,'ends':[dict(e['frame'],region=e['region']) for e in connection['ends']]})
    geography['verification']={'source':'shared global grid before partition','releaseRevision':'diagonal-spine-v1',
        'terrainRevisions':{r:manifests[r]['terrainRevision'] for r in world.ids},
        'sharedSurfaceSha256':digest(output/'shared-terrain.glb'),'masterSha256':digest(output/'continent.glb')}
    json_write(REGIONS/'continent-geography.json',geography)
    json_write(REGIONS/'continent-layout.json',{'schema':2,'continent':'Nymara','originMetres':[world.x0-40,world.z0-40],
        'canvasMetres':[world.x1-world.x0+80,world.z1-world.z0+80],'metresPerPixel':2,'sea':[43,95,109],
        'regions':{r:world.regions[r]['center'] for r in world.ids},'routeBends':{},
        'note':'One common-world master render; geographic centres label the named nonrectangular territories.'})


# Single-file digests composition.json records. A branch may add its own (an
# optional object-edit file beside the plan); every recorded digest is
# compared against the file it names, and anything unrecognised is reported.
COMPOSITION_INPUTS={'planSha256':('plan','diagonal-plan.json'),
    'entranceProfileSha256':('entranceProfile','legacy-server-profile/config/eloria/maps.txt'),
    'objectEditsSha256':('objectEdits','continent-edits.json')}


def composition_freshness(output=None):
    """Does the composition on disk still match the inputs it recorded?

    The same digests the compose and export stages refuse to work without,
    reported instead of raised, so an editor can show why a rebuild is due.
    Changed, missing and unrecognised inputs all read as stale. The verified
    content library is not covered: its cache path is a build argument the
    composition does not record.
    """
    output=Path(output) if output is not None else HERE/'generated'
    state={'fresh':False,'composed':False,'changed':[],'missing':[],'unknown':[],'recorded':{},'current':{}}
    path=output/'composition.json'
    if not path.exists():return state
    composition=json.loads(path.read_text(encoding='utf-8'));state['composed']=True
    def compare(name,recorded,current):
        state['recorded'][name]=recorded;state['current'][name]=current
        if current is None:state['missing'].append(name)
        elif recorded!=current:state['changed'].append(name)
    for key,(name,relative) in COMPOSITION_INPUTS.items():
        source=HERE/relative;current=digest(source) if source.exists() else None
        if composition.get(key) is None and current is None:continue
        compare(name,composition.get(key),current)
    compare('compositionAlgorithm',composition.get('compositionAlgorithmSha256'),composition_algorithm_sha())
    for relative,recorded in sorted(composition.get('sources',{}).items()):
        relative=relative.replace('\\','/')
        if Path(relative).name not in SHAPING_SOURCES:continue
        source=CLIENT/relative;compare(relative,recorded,digest(source) if source.exists() else None)
    for key,value in sorted(composition.items()):
        if key.endswith('Sha256') and key not in COMPOSITION_INPUTS and key!='compositionAlgorithmSha256':
            state['unknown'].append(key);state['recorded'][key]=value;state['current'][key]=None
    state['fresh']=not (state['changed'] or state['missing'] or state['unknown'])
    return state


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path)
    parser.add_argument('--output',type=Path,default=HERE/'generated')
    parser.add_argument('--stage',choices=['prepare','geometry','all'],default='all')
    parser.add_argument('--freshness',action='store_true',help='Report whether the composition still matches its inputs, then exit: 0 fresh, 1 stale, 2 nothing composed')
    args=parser.parse_args()
    if args.freshness:
        state=composition_freshness(args.output);print(json.dumps(state,indent=2))
        raise SystemExit(0 if state['fresh'] else 1 if state['composed'] else 2)
    if args.library is None:parser.error('--library is required to compose or export')
    args.output.mkdir(parents=True,exist_ok=True)
    PROGRESS.attach(args.output/'progress.json').watch()
    if args.stage in ('prepare','all'):world,content=prepare(args.library.resolve(),args.output.resolve())
    else:world,content=load_composed(args.output.resolve(),args.library.resolve())
    if args.stage in ('geometry','all'):export_geometry(world,content,args.output.resolve())
    PROGRESS.finish(0)

if __name__=='__main__':main()
