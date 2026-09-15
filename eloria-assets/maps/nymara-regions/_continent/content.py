"""Place retained authored structures and ecological instances in one world."""
from __future__ import annotations
import copy
import json
import math
import re
from pathlib import Path
import numpy as np
from scipy.interpolate import RegularGridInterpolator
from scipy.spatial import cKDTree
import landscape as L
import scene_io as S
import assemblies as A

NATURAL={'tree','foliage','rock','undergrowth','stone','scatter','small_dressing',
         'stump','fallenlog','leafdrift','mushrooms','fern','vine','scrub'}
METADATA=('landmarks','interactives','portals','spawnPoints','pointsOfInterest','harvestables','npcMarkers','creatureSpawns','spawns')
# Grey Moors survey fragments crossing the drainage that the continental
# bridge union now spans. Exactly these roots; see grey_crossings.py.
RETIRED_GREY_SPANS=('Landmark_boardwalk_gate','Landmark_boardwalk_centre','Landmark_boardwalk_south')
# A ground-standing prop whose base the regional survey left this far under
# its own terrain is stood on the ground when it is placed (see load()).
BURIED_PROP_METRES=.2
# A ground-standing prop the regional survey left this far in the air stands
# on the target ground too; hulls are settled on the actual water or ground by
# the boat modules, and props that float by design keep their authored offset.
FLOATING_PROP_METRES=.5
HULL_WORDS=('boat','skiff','dugout','canoe','punt','lateen','packet','tender','barge','raft','wherry')
FLOATING_BY_DESIGN=('wisp','light','flame','spark','orb','crystal','shard','lantern')
# Structures built to be passed keep the soft road clearance but are no solid
# for road alignment. Whole name words only: a shopfront on Four Gates street,
# a march track and an archive are solids, as are an arch's columns and a
# gate's walls and wings.
WALK_THROUGH_WORDS=('gate','arch','arcade','colonnade','causeway','portal','waygate')
WALK_THROUGH_EXCEPTIONS=('archcolumn','gatecolumn','gatewall','gatewing')


def name_words(name):
    """The whole words of a node name: separators and camel case both split ('Landmark_GreatArch' -> landmark, great, arch)."""
    return [w.lower() for w in re.findall(r'[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+',str(name))]


def walk_through(name):
    """A gate, arch, arcade, colonnade, causeway or portal, by the whole words of its node name."""
    if any(word in str(name).lower() for word in WALK_THROUGH_EXCEPTIONS):return False
    return any(word in WALK_THROUGH_WORDS for word in name_words(name))


def retained_source_placements(region, placements):
    """Discard Manymouth's former inter-district route assemblies as roots.

    Its source layout.py/compact_plan.py emit Survey_<from>__<to> parents
    containing Walk_Survey_* ribbons. The continent authors those routes again;
    retaining the parent accidentally preserves aerial floors despite filtering
    standalone Walk nodes. Landing_* platforms and real architecture remain.
    Filter before assembly grouping so discarded route bounds cannot move a town.
    """
    obsolete={'manymouth_delta':('Survey_','Walk_Survey_'),
              'mirrorhold':('Landmark_MeltwaterBridge_',),
              # Whitehorn's boundary marches dressed the old map's exits; under the
              # retained transform they stand in the continent's seam zones at the
              # relief's edge, where the seam roads are the exits.
              'whitehorn_range':('Landmark_rope_bridge_','March_west_pass_','March_east_pass_','March_south_gate_'),
              'amberwood':('Landmark_Survey_ridge-bridge',)}
    # Wilderness spans were surveyed against the retired regional ravines.
    # Their new crossings are built from the continent's actual drainage.
    # Named discoveries at the old bridge abutments retain their own geometry.
    # Grey Moors keeps its other spans, causeway bridges and boardwalk cache;
    # only the three duplicate crossings are retired, by exact root name.
    # The Whitehorn north shrine stood on the old map's crest beyond the continent's
    # north edge; under the retained transform it lands on the shore two metres
    # from the sea with a 164 m legacy footing. Retired until the crest returns.
    retired={'grey_moors':set(RETIRED_GREY_SPANS),'whitehorn_range':{'Landmark_shrine_01'}}
    return [p for p in placements if not p['node'].startswith(obsolete.get(region,())) and p['node'] not in retired.get(region,())]


def spawn_position(template):
    spawns=template.get('spawnPoints',template.get('spawns',[]))
    default=template.get('navigation',{}).get('defaultSpawn')
    chosen=next((s for s in spawns if s.get('id')==default or s.get('default')),spawns[0] if spawns else {'position':[0,0,0]})
    return np.array(chosen.get('position',[0,0,0]),float)


class Content:
    def __init__(self,world,library,templates,legacy):
        self.world=world;self.library=Path(library);self.templates=templates;self.legacy=legacy
        self.documents={};self.metadata={};self.prototypes={};self.objects=[];self.mapping={};self.source_centers={};self.scales={}
        self.placement_by_name={};self.bounds_by_name={}
        self.companions={}
        self.assembly_records={}
        self.ids=world.ids

    def mapped_xz(self,region,points):
        points=np.asarray(points,float)
        return (points-self.source_centers[region])*self.scales[region]+self.world.regions[region]['center']

    def solid_boxes(self):
        """Retained colliding solids no road alignment should cross: (region, node, low, high)."""
        return [(o['region'],o['node'],np.asarray(o['low'],float),np.asarray(o['high'],float))
                for o in self.objects if o.get('collides') and not o.get('walk') and o.get('kind') not in A.NATURE]

    def register_obstacles(self):
        """Register every retained colliding structure with the router where it finally stands.

        Runs after the prepare stages have moved what they move (the Amberwood
        stall row, the props cleared off the market stair and root ramp strips):
        a structure registered at load and moved afterwards leaves the router
        a phantom solid where nothing stands and none where the structure
        does, and the fifteenth's hub roads were aligned through two moved
        market stalls. With the structures registered where they stand the
        Amberwood hub roads leave the platform east, the cinder chapel door
        road takes a direct line up the hill (234 m, a 21 m cut, in place of a
        495 m loop with a 45 m cut) and the discovery branches south of the
        Great Tree move with them; the Motherroot Voice, whose root plateau
        one of those branches used to reach, stands at the Motherroot mouth
        (amberwood_access.MOTHERROOT_VOICE_POST), and the root ramp joins the
        plateau to the village yard. A gate, arch, arcade, colonnade, causeway
        or portal is built to be passed: it keeps the soft clearance but is no
        solid for alignment.
        """
        count=0
        for o in self.objects:
            if o.get('collides') and not o.get('walk'):
                self.world.structure_obstacle(o['low'],o['high'],solid=not walk_through(o['node']));count+=1
        return count

    def load(self):
        for region in self.ids:
            folder=self.library/region
            document,body=S.GR.load(folder/'library.glb')
            metadata=json.loads((folder/'library.json').read_text())
            metadata['placements']=retained_source_placements(region,metadata['placements'])
            if region=='amberwood':
                from amberwood_access import prepare_camp_source
                document,metadata=prepare_camp_source(document,body,metadata,folder)
            self.documents[region]=(document,body)
            self.metadata[region]=metadata
            matrices,parents=S.GR.hierarchy(document)
            by_name={n.get('name'):i for i,n in enumerate(document['nodes'])}
            foliage={}
            for placement in metadata['placements']:
                if placement.get('kind')=='foliage' and placement['node'] in by_name:
                    foliage.setdefault(tuple(np.round(placement['position'],4)),[]).append(by_name[placement['node']])
            attached_foliage=set()
            for placement in metadata['placements']:
                if placement.get('kind')=='tree' or placement['node'].endswith('_Wood'):
                    attached_foliage.update(foliage.get(tuple(np.round(placement['position'],4)),[]))
            # Geographic centres are territory labels; the inhabited arrival is
            # the retained local composition's datum within that territory.
            center=spawn_position(self.templates[region])[[0,2]]
            self.source_centers[region]=center
            self.scales[region]=.78 if region!='four_gates' else .90
            region_transform=self.world.plan.get('retained_transforms',{}).get(region)
            if region_transform:
                self.scales[region]=1.
                self.source_centers[region]=np.asarray(self.world.regions[region]['center'])-np.asarray(region_transform)[[0,2]]
            ground=np.load(folder/'foundation-samples.npz')
            sample=RegularGridInterpolator((ground['z'],ground['x']),ground['height'],bounds_error=False,fill_value=None)
            def source_height(x,z):
                x,z=np.broadcast_arrays(np.asarray(x,float),np.asarray(z,float))
                return sample(np.c_[z.ravel(),x.ravel()]).reshape(x.shape)
            source_bounds={p['node']:S.subtree_bounds(document,body,by_name[p['node']],matrices)
                           for p in metadata['placements'] if p['node'] in by_name}
            groups=A.build_assemblies(region,metadata['placements'],source_bounds,source_height)
            group_shifts={}
            for identity,assembly in groups.items():
                site=self.world.plan.get('assembly_sites',{}).get(identity,{})
                authored_transform=site.get('translation',region_transform)
                shift=assembly.shift_to(lambda p:self.mapped_xz(region,p),self.world.height_at,
                    water_level=site.get('water_level',0.),target_xz=site.get('center'))
                if authored_transform is not None:
                    # An explicit authored relocation, such as a discovery
                    # moved into an accessible side gallery, keeps every
                    # linked point and all of its geometry on one transform.
                    shift=np.asarray(authored_transform,float).copy()
                    if shift.shape!=(3,) or not np.isfinite(shift).all():
                        raise ValueError(identity+': authored translation must contain three finite metres')
                # Move a whole compound when an edge would leave its territory.
                # No component acquires a private XZ or vertical correction.
                hub=np.asarray(self.world.regions[region]['center'],float)
                member_points=np.array([[x,z] for node in assembly.nodes
                    for x in (source_bounds[node][0][0],source_bounds[node][1][0])
                    for z in (source_bounds[node][0][2],source_bounds[node][1][2])])
                for _ in range(0 if authored_transform is not None else 32):
                    points=member_points+shift[[0,2]]
                    if np.all(self.world.owner_at(points[:,0],points[:,1])==self.ids.index(region)):break
                    target=assembly.reference_xz+shift[[0,2]];shift[[0,2]]+=(hub-target)*.08
                if authored_transform is None and assembly.datum=='terrain':
                    anchor=assembly.reference_xz+shift[[0,2]]
                    shift[1]=float(self.world.height_at(*anchor))-assembly.reference_y
                group_shifts[identity]=shift
                self.assembly_records[identity]=dict(A.report(assembly),translation=shift.tolist())
                feather=32. if identity=='mirrorhold.city' else 24.
                margin=feather+12.
                low=assembly.bounds[0,[0,2]]+shift[[0,2]]-margin;high=assembly.bounds[1,[0,2]]+shift[[0,2]]+margin
                ix0=max(0,int((low[0]-self.world.x0)/2));ix1=min(len(self.world.x),int((high[0]-self.world.x0)/2)+2)
                iz0=max(0,int((low[1]-self.world.z0)/2));iz1=min(len(self.world.z),int((high[1]-self.world.z0)/2)+2)
                sl=np.s_[iz0:iz1,ix0:ix1]
                target,weight=assembly.sample_foundation(self.world.gx[sl],self.world.gz[sl],shift,source_height,feather=feather)
                if region=='manymouth_delta' and assembly.datum=='water':
                    # Stilt floors sit above wet ground. Legacy survey terraces
                    # cannot become banks poking through their intact porches.
                    target=np.minimum(target,shift[1]+1.)
                if identity in ('manymouth_delta.north_fishing','manymouth_delta.paddy_hamlet',
                                'manymouth_delta.west_hamlet','manymouth_delta.east_hamlet'):
                    # These intact groups occupy real low coast or upper banks.
                    # Their former regional surveys contain deep trenches;
                    # retain the natural seabed and only lower occupied bank
                    # beneath the stilt floors, with the normal soft apron.
                    target=np.minimum(self.world.original_height[sl],shift[1]+1.)
                    if identity=='manymouth_delta.east_hamlet':
                        # The occupied upper-bank yards share one soil datum.
                        # Fill the slightly lower lore-court end as well as
                        # cutting the hillward side; keep the local footprint
                        # mask and feather instead of making a rectangular pad.
                        target=np.full(target.shape,shift[1]+1.)
                self.world.assembly_foundation(sl,target,weight)
            retained=[];natural=[]
            for p in metadata['placements']:
                index=by_name.get(p['node'])
                if index is None: continue
                name=p['node'];kind=p.get('kind','prop')
                if kind=='foliage' and index in attached_foliage:continue
                assembly_id=A.placement_group(region,p,metadata['placements'])
                if name.startswith('Walk_Survey_'):continue
                if any(token in name for token in ('_Stream','StreamView_','Backdrop_')) or name.startswith(('March_','MarchGate_')): continue
                low,high=S.subtree_bounds(document,body,index,matrices)
                if kind=='tree' or name.endswith('_Wood'):
                    companions=foliage.get(tuple(np.round(p['position'],4)),[])
                    self.companions[(region,index)]=companions
                    for companion in companions:
                        c_low,c_high=S.subtree_bounds(document,body,companion,matrices)
                        low=np.minimum(low,c_low);high=np.maximum(high,c_high)
                if not np.isfinite(low).all():continue
                if kind in NATURAL and not p.get('landmark') and not assembly_id:
                    if kind in ('tree','rock','fern','undergrowth','scrub','stump','fallenlog','mushrooms','leafdrift') and .05<high[1]-low[1]<30: natural.append((p,index,low,high))
                    continue
                # Former regional paths are replaced by continent roads. Keep
                # architectural floors, bridges, streets and named discoveries.
                if not p.get('landmark') and (kind in ('road','path','terrain','ground') or name.startswith(('Road_','Path_','Track_','Soil_','Walk_Road_','Walk_Path_','Walk_Track_'))):continue
                pivot=(low+high)*.5
                old_xz=pivot[[0,2]]
                new_xz=self.mapped_xz(region,old_xz)
                owner=int(self.world.owner_at(*new_xz));expected=self.ids.index(region)
                # Pull peripheral decorative structures inside their named
                # territory. The exact displacement follows linked metadata.
                hub=np.array(self.world.regions[region]['center'],float)
                radius=float(np.linalg.norm((high-low)[[0,2]])*.5)
                for _ in range(0 if assembly_id else 24):
                    samples=np.array([new_xz+[dx,dz] for dx,dz in ((0,0),(radius+3,0),(-radius-3,0),(0,radius+3),(0,-radius-3))])
                    owned=np.all(self.world.owner_at(samples[:,0],samples[:,1])==expected)
                    aquatic=any(word in name.lower() for word in ('boat','skiff','pier','jetty','quay','bridge','causeway','sunken','waterfall'))
                    ground_height=float(self.world.height_at(*new_xz))
                    wet=L.water_fields(*new_xz,height=ground_height,plan=self.world.plan)
                    dry=aquatic or (ground_height>.8 and not (wet['mask'] and wet['depth']>.35))
                    if owned and dry:break
                    new_xz=hub+(new_xz-hub)*.90
                source_ground=float(sample([[old_xz[1],old_xz[0]]])[0])
                # Regional surveys left some ground-standing props buried in
                # their own terrain (Whitehorn cairns up to 30 m under it). A
                # compact prop whose base lies under the legacy ground stands
                # on the ground here. Props above the ground may rest on decks
                # or rocks and keep their authored offset, as do landmarks,
                # buildings and buried crystals; hulls are settled on water.
                hull=any(word in name.lower() for word in HULL_WORDS)
                if kind=='prop' and not assembly_id and not hull and source_ground-float(low[1])>BURIED_PROP_METRES:
                    source_ground=float(low[1])-.02
                elif (kind=='prop' and not assembly_id and not hull and float(low[1])-source_ground>FLOATING_PROP_METRES
                      and not any(word in name.lower() for word in FLOATING_BY_DESIGN)):
                    source_ground=float(low[1])-.02
                target_ground=float(self.world.height_at(*new_xz))
                # Large inhabited compounds retain their internal grade. The
                # continent supplies a broad landing around their footprint.
                if region in ('manymouth_delta','crownwater') and source_ground<1.5 and target_ground<1.5:
                    target_ground=max(-1.,min(target_ground,1.))
                else:target_ground=max(.8,target_ground)
                shift=np.array([new_xz[0]-old_xz[0],target_ground-source_ground,new_xz[1]-old_xz[1]])
                if assembly_id:
                    shift=group_shifts[assembly_id].copy();new_xz=old_xz+shift[[0,2]]
                    target_ground=source_ground+shift[1]
                    if region=='manymouth_delta' and groups[assembly_id].datum=='water':target_ground=min(source_ground,1.)+shift[1]
                all_names={document['nodes'][i].get('name','') for i in S.descendants(document,[index])}
                obj={'region':region,'index':index,'indices':[index,*self.companions.get((region,index),[])],'shift':shift,'low':low+shift,'high':high+shift,
                     'kind':kind,'node':name,'names':all_names,'collides':p.get('collides',False),
                     'walk':p.get('walk_surface',False),'source':p,'sourcePivot':pivot,'targetGround':target_ground}
                if assembly_id:obj['assembly']=assembly_id
                retained.append(obj)
                self.mapping[(region,name)]=shift
                self.placement_by_name[(region,name)]=obj
                self.bounds_by_name[(region,name)]=(low+shift,high+shift)
                # Obstacles reach the router through register_obstacles once the
                # prepare stages have moved what they move (build_continent,
                # before plan_connections).
                # Avoid raising seabed for docks; their piers are authored to
                # support the walk surface above the common estuary water.
                if not assembly_id and (source_ground>=1.5 or target_ground>=1.5 or region not in ('manymouth_delta','crownwater')):
                    footprint=min(38,max(2,radius*.72))
                    self.world.foundation(new_xz,footprint,target_ground,feather=max(12,footprint*.7),obstacle=p.get('collides',False) and not p.get('walk_surface',False))
            self.objects.extend(retained)
            self.prototypes[region]=natural
            print(f'{region}: retained {len(retained)} structures/landmarks, {len(natural)} natural prototypes',flush=True)

    def mapped_point(self,region,point,node=None,landmark=None):
        point=np.array(point,float)
        shift=self.mapping.get((region,node)) if node else None
        if shift is None and landmark:
            entry=next((p for p in self.metadata[region]['placements'] if p.get('landmark')==landmark),None)
            if entry:shift=self.mapping.get((region,entry['node']))
        if shift is None:
            nearby=[]
            for obj in self.objects:
                if obj['region']!=region or obj.get('kind') in NATURAL or 'sourcePivot' not in obj:continue
                low=obj['low']-obj['shift'];high=obj['high']-obj['shift']
                outside=np.maximum(np.maximum(low[[0,2]]-point[[0,2]],point[[0,2]]-high[[0,2]]),0)
                distance=float(np.linalg.norm(outside))
                if distance<=24:nearby.append((distance+.005*np.linalg.norm(point[[0,2]]-obj['sourcePivot'][[0,2]]),obj['shift']))
            if nearby:
                candidate=min(nearby,key=lambda p:p[0])[1]
                mapped=point+candidate
                if int(self.world.owner_at(mapped[0],mapped[2]))==self.ids.index(region):shift=candidate
        if shift is not None:return point+shift
        x,z=self.mapped_xz(region,point[[0,2]])
        hub=np.asarray(self.world.regions[region]['center'],float)
        for _ in range(40):
            h=float(self.world.height_at(x,z))
            water=L.water_fields(x,z,height=h,plan=self.world.plan)
            if int(self.world.owner_at(x,z))==self.ids.index(region) and not (water['mask'] and water['depth']>.35):break
            x,z=hub+(np.array([x,z])-hub)*.90
        return np.array([x,float(self.world.height_at(x,z)),z])

    def mapped_server_point(self,region,tile):
        """Use the authoritative tile and its linked architectural transform."""
        authored=getattr(self,'authored_server_points',{}).get((region,tuple(tile)))
        if authored is not None:return np.asarray(authored,float).copy()
        entries=[]
        def visit(value):
            if isinstance(value,list):
                for entry in value:visit(entry)
            elif isinstance(value,dict):
                old=value.get('serverTile',value.get('server_tile'))
                if old is not None and tuple(old)==tuple(tile):entries.append(value)
                for entry in value.values():
                    if isinstance(entry,(dict,list)):visit(entry)
        visit(self.templates[region])
        entry=next((e for e in entries if e.get('doorNode') or e.get('node')),entries[0] if entries else {})
        origin=self.templates[region]['coordinateTransform']['serverOrigin']
        point=[tile[0]+.5-origin[0],0.,origin[1]-tile[1]-.5]
        return self.mapped_point(region,point,entry.get('node',entry.get('doorNode')),entry.get('landmark'))

    def reground(self):
        """Settle footings after overlapping village terraces and roads agree."""
        for obj in self.objects:
            if obj.get('assembly'):continue
            pivot=(obj['low']+obj['high'])*.5
            difference=float(self.world.height_at(pivot[0],pivot[2]))-obj['targetGround']
            obj['shift'][1]+=difference;obj['low'][1]+=difference;obj['high'][1]+=difference
            obj['targetGround']+=difference
            self.bounds_by_name[(obj['region'],obj['node'])]=(obj['low'],obj['high'])
        for identity in self.assembly_records:
            A.assert_rigid([obj for obj in self.objects if obj.get('assembly')==identity])

    def ecological_scatter(self):
        rng=np.random.default_rng(self.world.plan['seed']+481)
        xs=np.arange(self.world.x0+6,self.world.x1,9.)
        zs=np.arange(self.world.z0+6,self.world.z1,9.)
        gx,gz=np.meshgrid(xs,zs)
        x=gx.ravel()+rng.uniform(-3.8,3.8,gx.size);z=gz.ravel()+rng.uniform(-3.8,3.8,gz.size)
        h=self.world.height_at(x,z)
        ec=L.vegetation_fields(x,z,height=h,plan=self.world.plan)
        road=triangle_road(self.world,x,z)
        blocked=self.world.obstacles[np.clip(((z-self.world.z0)/2).astype(int),0,len(self.world.z)-1),np.clip(((x-self.world.x0)/2).astype(int),0,len(self.world.x)-1)]
        wet=L.water_fields(x,z,height=h,plan=self.world.plan)
        slope=np.hypot((self.world.height_at(x+2,z)-self.world.height_at(x-2,z))/4,(self.world.height_at(x,z+2)-self.world.height_at(x,z-2))/4)
        count=0
        for i in np.flatnonzero((rng.random(len(x))<np.clip(ec['tree_density'],0,1)) & (h>.8)&(~wet['mask'])&(road>1.9)&(~blocked)&(slope<.65)):
            region=self.ids[int(self.world.owner_at(x[i],z[i]))]
            if ec['conifer'][i]>.45: source='whitehorn_range'
            elif z[i]>980 and x[i]>800:source='verdant_stair' if rng.random()<.6 else 'ssarathi_ruins'
            elif ec['dryness'][i]>.55:source='sunmane_steppe'
            elif ec['deciduous'][i]>.4:source='amberwood' if rng.random()<.7 else 'grey_moors'
            else:source='grey_moors'
            pool=[p for p in self.prototypes.get(source,[]) if p[0]['kind']=='tree']
            if not pool:continue
            p,index,low,high=pool[int(rng.integers(len(pool)))]
            center=(low+high)*.5
            # Root contact uses the lower trunk, not the placement origin.
            shift=np.array([x[i]-center[0],h[i]-low[1]+.025,z[i]-center[2]])
            doc,_=self.documents[source]
            count+=1
            self.objects.append({'region':region,'libraryRegion':source,'index':index,'shift':shift,
                'indices':[index,*self.companions.get((source,index),[])],
                'low':low+shift,'high':high+shift,'kind':'tree','node':f'Grove_{count:05d}',
                'nodePrefix':f'Grove_{count:05d}_','names':set(),'collides':False,'walk':False})
        print(f'Continental ecology: {count} trees placed in moist, sheltered, clear ground',flush=True)
        formations=0
        # A few exposed outcrops and their related debris, with generous quiet
        # ground between them. Regional libraries keep their geology/materials.
        candidates=(h>1)&(~wet['mask'])&(road>3)&(~blocked)&(slope>.16)&(slope<.62)
        for i in np.flatnonzero(candidates & (rng.random(len(x))<.028)):
            region=self.ids[int(self.world.owner_at(x[i],z[i]))]
            pool=[p for p in self.prototypes.get(region,[]) if p[0]['kind']=='rock']
            if not pool:continue
            pool=sorted(pool,key=lambda p:np.prod(p[3]-p[2]))
            selected=[pool[int(rng.integers(max(1,len(pool)//2),len(pool)))]] if len(pool)>1 else pool
            selected+= [pool[int(rng.integers(max(1,len(pool)//2)))]] * int(rng.integers(1,4))
            formations+=1
            for j,(p,index,low,high) in enumerate(selected):
                xx=x[i]+(rng.uniform(-4,4) if j else 0);zz=z[i]+(rng.uniform(-4,4) if j else 0)
                if int(self.world.owner_at(xx,zz))!=self.ids.index(region):continue
                y=float(self.world.height_at(xx,zz));center=(low+high)*.5
                shift=np.array([xx-center[0],y-low[1]-.12,zz-center[2]])
                self.objects.append({'region':region,'libraryRegion':region,'index':index,'shift':shift,
                    'low':low+shift,'high':high+shift,'kind':'rock','node':f'Outcrop_{formations:04d}_{j}',
                    'nodePrefix':f'Outcrop_{formations:04d}_{j}_','names':set(),'collides':False,'walk':False})
        print(f'Continental geology: {formations} related rock formations',flush=True)
        undergrowth=0
        pockets=(h>.8)&(~wet['mask'])&(road>2.2)&(~blocked)&(slope<.5)&(ec['tree_density']>.20)
        for i in np.flatnonzero(pockets & (rng.random(len(x))<.13)):
            region=self.ids[int(self.world.owner_at(x[i],z[i]))]
            source='verdant_stair' if z[i]>980 and x[i]>800 else ('amberwood' if ec['deciduous'][i]>.3 else region)
            pool=[p for p in self.prototypes.get(source,[]) if p[0]['kind'] in ('fern','undergrowth','stump','fallenlog','mushrooms','leafdrift')]
            if not pool:continue
            p,index,low,high=pool[int(rng.integers(len(pool)))];center=(low+high)*.5
            shift=np.array([x[i]-center[0],h[i]-low[1]-.025,z[i]-center[2]])
            undergrowth+=1
            self.objects.append({'region':region,'libraryRegion':source,'index':index,'shift':shift,
                'low':low+shift,'high':high+shift,'kind':'undergrowth','node':f'WoodlandFloor_{undergrowth:04d}',
                'nodePrefix':f'WoodlandFloor_{undergrowth:04d}_','names':set(),'collides':False,'walk':False})
        print(f'Continental woodland floor: {undergrowth} sheltered undergrowth pockets',flush=True)


def triangle_road(world,x,z):
    from world_layout import triangle_sample
    distance=np.where(np.isfinite(world.road_distance),world.road_distance,1e6)
    return triangle_sample(distance,x,z,world.x0,world.z0)
