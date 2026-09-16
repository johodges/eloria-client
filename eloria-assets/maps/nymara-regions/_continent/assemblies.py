"""Rigid placement of authored compounds, with local terrain support patches.

Call placement_group before discarding small_dressing: signs, lamps and rails
belong to their streets. Build each group's bounds from actual library GLB
subtrees. Apply ONE translation to every member, its metadata, and walk meshes;
never compress member pivots while retaining full-size geometry. A later
reground pass may move the whole assembly, never its individual pieces.

This module supplies geometry-independent placement contracts and bounded
foundation fields. It does not edit content, terrain, meshes or publications.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable, Mapping

import numpy as np
from scipy.spatial import ConvexHull
import westhaven_support as W
import manymouth_support as D


NATURE = {'tree','foliage','rock','undergrowth','stone','scatter','stump',
          'fallenlog','leafdrift','mushrooms','fern','vine','scrub'}
HAMLETS = ('paddy_hamlet','east_hamlet','south_hamlet','west_hamlet','north_fishing',
           'boat_yard','far_bar','sea_landing','temple_quay','deep_grove')
TOWN_LINKS = {'Survey_stilt_town__town_hall','Survey_stilt_town__town_quay',
              'Survey_stilt_town__market_hall','Survey_market_hall__floating_market'}
TOWN_NODES = {'Landmark_MootHall','Landmark_MarketHall','Landing_stilt_town',
              'Landing_floating_market','PacketLateen','Secret_delta_moot_vault'}
MIRROR_FORTRESS = ('Landmark_Orrery','Landmark_Citadel','Landmark_Basin_',
    'Landmark_Gate','Landmark_Gallery','Landmark_RoseWindow','Landmark_lens_tower_',
    'Landmark_north-post','Landmark_upper-shrine','Building_VaultEntry_lens-',
    'Prop_Brazier_0_','Prop_Brazier_2_','Secret_mirror_orrery_','Secret_mirror_rose_',
    'Secret_mirror_basin_','Secret_mirror_citadel_','Secret_mirror_lens_focus',
    'Secret_mirror_icebore_')
REFERENCE = {'four_gates.civic':((0.,0.),'terrain'),
    'four_gates.sanctuary':((-115.,-162.),'terrain'),
    'four_gates.south-gate':((.5,172.),'terrain'),
    'crownwater.causeway-city':((23.,8.),'water'),
    'mirrorhold.fortress':((99.6788,-138.6464),'terrain'),
    'mirrorhold.plaza':((69.6788,-39.6464),'terrain'),
    'mirrorhold.lake-harbour':((93.6788,42.4641),'water'),
    'amberwood.canopy-village':((61.2229,-141.8745),'terrain'),
    'amberwood.great-arch':((132.9427,-49.1381),'terrain'),
    'amberwood.garden':((122.2803,29.841),'terrain'),
    'sunmane_steppe.encampment':((0.,0.),'terrain'),
    'amberwood.ridge-camp':((161.3758,-224.9205),'terrain'),
    'manymouth_delta.boardwalk-town':((39.3459,-55.3715),'water'),
    'manymouth_delta.east_hamlet':((292.06279895504485,-120.97237631493502),'terrain')}
REFERENCE.update(W.REFERENCES)
REFERENCE.update(D.REFERENCES)
# The upper-bank hamlet retains the old tidal architectural datum. Sampling
# its obsolete excavated seabed (-4m) would lift every stilt floor needlessly.
REFERENCE_HEIGHTS={'manymouth_delta.east_hamlet':0.}


def placement_group(region, placement, allplacements=()):
    """Stable assembly ID, or None for a separate wilderness object.

    Explicit source assembly metadata takes precedence. Legacy recipes have
    meaningful component names, including zero-origin baked walk meshes;
    membership therefore must not be inferred from placement-position alone.
    """
    explicit=placement.get('assembly') or placement.get('assembly_id')
    if explicit:return region+'.'+str(explicit)
    name=placement['node'];kind=placement.get('kind','prop')
    if region=='westhaven':return W.placement_group(placement)
    if region=='amberwood' and name.startswith('Landmark_Giant_'):return 'amberwood.canopy-village'
    if kind in NATURE:return None
    if any(token in name for token in ('_Stream','StreamView_','Backdrop_')) or name.startswith(('March_','MarchGate_','Walk_Survey_')):
        return None
    if region=='mirrorhold' and kind not in ('road','path','ground','terrain'):
        return 'mirrorhold.city'
    if region=='four_gates':
        if name.startswith(('Northern_Sanctuary','Sanctuary_','Walk_Sanctuary_')) or name=='Secret_gates_sanctuary_reliquary':
            return region+'.sanctuary'
        if name.startswith(('Gate_South_Outer','SouthOuter_')):return region+'.south-gate'
        if name.startswith(('Plaza_','Shopfront_','District_House_','City_Wall_',
            'Gate_','Market_','Avenue_','Sign_four-gates-','Goods_four-gates-')):
            return region+'.civic'
        if name.startswith(('Secret_gates_','Garden_Rail_')):
            point=placement.get('position',[math.inf,0,math.inf])
            if math.hypot(point[0],point[2])<=125:return region+'.civic'
    elif region=='crownwater':
        # The complete radial causeway network, islands, quays and their
        # architectural dressing share one sea-level datum. This includes
        # baked Causeway roots whose placement Y is deliberately zero.
        if name=='Walk_FourGatesNativeLanding':return None
        if kind not in ('road','path','ground','terrain'):return region+'.causeway-city'
    elif region=='mirrorhold':
        if name.startswith(MIRROR_FORTRESS):return region+'.fortress'
        if name.startswith(('Landmark_Fountain','Landmark_PlazaStatue_','Prop_PlazaLamp_',
                            'Building_VaultEntry_cistern-','Secret_mirror_waystone','Prop_Brazier_1_')):
            return region+'.plaza'
        if name.startswith(('Landmark_Ring','Landmark_LakeLink_','Landmark_Quay','Landmark_Dock_',
                            'Prop_Boat_','Prop_Pier','Prop_HarbourGoods_')):
            return region+'.lake-harbour'
        if name.startswith('Building_CliffHouse_'):
            return region+'.cliff-row-'+str(int(name.rsplit('_',1)[1])//5)
    elif region=='amberwood':
        if name=='Landmark_Watchtower_1' or name.startswith(('Prop_Tent_ridge_camp_','Brazier_ridge_camp_')):
            return region+'.ridge-camp'
        if name.startswith(('Landmark_Canopy','Landmark_GreatTree_')):return region+'.canopy-village'
        if name.startswith(('Landmark_GreatArch','Landmark_ArchColumn_')):return region+'.great-arch'
        if name.startswith('Landmark_Garden'):return region+'.garden'
    elif region=='manymouth_delta':
        if name=='Landing_shore_south_hamlet':return region+'.south_hamlet'
        if name in ('Lore_stelae_court','Landing_lore_court','Landing_shore_lore_court'):
            return region+'.east_hamlet'
        compound=D.placement_group(name)
        if compound:return compound
        if name.startswith(('town_','market_stall_','MooredMarketBoat_')) or name in TOWN_NODES|TOWN_LINKS:
            return region+'.boardwalk-town'
        for hamlet in HAMLETS:
            if name.startswith(hamlet+'_') or name=='Landing_'+hamlet:return region+'.'+hamlet
        # Exterior standing stones follow the final bank, not the temple's
        # raised floor datum; they do not carry connected walk geometry.
    elif region=='sunmane_steppe':
        if name.startswith('Encampment_') or name in (
            'Structure_Palisade','Landmark_sunmane_great_hall','Landmark_sunmane_well_00',
            'Landmark_sunmane_secret_steppe-hall-vault',
            *('Landmark_orun_banner_shrine_'+str(i).zfill(2) for i in range(4,8))):
            return region+'.encampment'
    elif region=='ssarathi_ruins':
        if name=='Secret_ruins_temple_focus':return region+'.temple-focus'
        # The pyramid, canal courts, outer shrines and water gate share a
        # surveyed plan. Separate compacted pivots put the lily court inside
        # the pyramid and the culvert beneath its stairs.
        if kind not in ('road','path','ground','terrain'):return region+'.ruin-city'
    return None


def supports_ground(placement):
    """A bridge deck or water surface is not an island-shaped foundation."""
    name=placement['node'].lower()
    if placement.get('kind') in NATURE:return False
    if name.startswith(('landmark_canopyplatform','landmark_canopywalkway')):return False
    if any(word in name for word in ('boat','skiff','lateen','causeway','pier','quay','survey_',
        'water','sunken','lamp','bollard','banner','crystal','flame','portcullis')):return False
    return not name.startswith(('prop_','secret_','sign_','goods_','plaza_bench','plaza_fountain','plaza_arcade'))


@dataclass
class Assembly:
    id: str
    nodes: tuple[str,...]
    reference_xz: np.ndarray
    reference_y: float
    datum: str
    bounds: np.ndarray
    footprints: tuple[np.ndarray,...]

    def shift_to(self, map_xz: Callable, target_height: Callable, *, water_level=0., target_xz=None):
        """Map the assembly anchor once; preserve metre-for-metre structure."""
        target=np.asarray(map_xz(self.reference_xz) if target_xz is None else target_xz,float)
        y=float(water_level if self.datum=='water' else target_height(*target))
        return np.array([target[0]-self.reference_xz[0],y-self.reference_y,target[1]-self.reference_xz[1]])

    def sample_foundation(self, x, z, shift, source_height, *, feather=12., unmap=None):
        """Return target Y and influence for footprint-local original grades.

        Query with world XZ arrays on the new global terrain lattice. Source
        height takes source X,Z arrays. Blend once using maximum influence,
        not one additive raising pass per component. Open water and bridge
        spans stay outside the support mask. The original region's terrain is
        sampled only underneath buildings/yards, never copied as a rectangle.
        ``unmap`` (a turned layout's inverse mapping) carries the sample point back to the legacy
        frame, which the shift alone cannot do once the layout turns; without it the shift leads
        back, as it does for every territory that is only translated.
        """
        if not math.isfinite(feather) or feather<=0:raise ValueError('Foundation feather must be positive')
        x,z=np.broadcast_arrays(np.asarray(x,float),np.asarray(z,float))
        sx,sz=x-shift[0],z-shift[2]
        influence=np.zeros(x.shape,float)
        for footprint in self.footprints:
            low,high=footprint
            dx=np.maximum(np.maximum(low[0]-sx,sx-high[0]),0)
            dz=np.maximum(np.maximum(low[1]-sz,sz-high[1]),0)
            t=np.clip(1-np.hypot(dx,dz)/feather,0,1)
            influence=np.maximum(influence,t*t*(3-2*t))
        sample_x,sample_z=sx,sz
        if self.id=='mirrorhold.city' and len(self.footprints)>1:
            # The fortress, cliff streets and harbour occupy one inhabited
            # hillside. Preserve the surveyed streets BETWEEN their buildings
            # too; isolated footprint patches create pits and bury the quays.
            # The old survey is authoritative inside this inhabited envelope.
            # Beyond it, extend its boundary elevation only through the local
            # apron. Sampling the distant old mountain here used to raise an
            # empty Four Gates hillside by 70 m.
            corners=np.array([[a,b] for low,high in self.footprints
                for a in (low[0],high[0]) for b in (low[1],high[1])])
            hull=ConvexHull(corners)
            signed=np.full(x.shape,-np.inf)
            for nx,nz,offset in hull.equations:
                signed=np.maximum(signed,nx*sx+nz*sz+offset)
            distance=np.full(x.shape,np.inf)
            nearest_x=sx.copy();nearest_z=sz.copy()
            vertices=corners[hull.vertices]
            for a,b in zip(vertices,np.roll(vertices,-1,axis=0)):
                delta=b-a
                t=np.clip(((sx-a[0])*delta[0]+(sz-a[1])*delta[1])/np.dot(delta,delta),0,1)
                px,pz=a[0]+t*delta[0],a[1]+t*delta[1]
                d=np.hypot(sx-px,sz-pz);closer=d<distance
                nearest_x=np.where(closer,px,nearest_x);nearest_z=np.where(closer,pz,nearest_z)
                distance=np.minimum(distance,d)
            outside=signed>1e-8
            distance=np.where(outside,distance,0.)
            t=np.clip(1-distance/feather,0,1)
            influence=t*t*(3-2*t)
            sample_x=np.where(outside,nearest_x,sx);sample_z=np.where(outside,nearest_z,sz)
        if unmap is not None:
            # A turned layout: the legacy ground under this footing is the continent point carried back
            # through the layout's own mapping, not the point the shift alone reaches.
            sample_x,sample_z=unmap(sample_x+shift[0],sample_z+shift[2])
        target=np.asarray(source_height(sample_x,sample_z),float)+shift[1]
        return target,influence


def build_assemblies(region, placements, bounds_by_name: Mapping, source_height: Callable, references=None):
    """Build groups from actual source-space GLB bounds; return ID -> Assembly.

    bounds_by_name[node] is (minimumXYZ, maximumXYZ). source_height(x,z)
    supports scalar or broadcast NumPy input. Regions are never mutated here.
    ``references`` pins a compound's anchor to the point it stood on before its layout was turned, so
    turning the compound about that anchor cannot move the compound itself.
    """
    groups={}
    for p in placements:
        identity=placement_group(region,p,placements)
        if identity and p['node'] in bounds_by_name:groups.setdefault(identity,[]).append(p)
    result={}
    for identity,members in groups.items():
        bounds=np.array([bounds_by_name[p['node']] for p in members],float)
        if not np.isfinite(bounds).all() or np.any(bounds[:,1]<bounds[:,0]):raise ValueError(identity+': invalid actual assembly bounds')
        full=np.array([bounds[:,0].min(axis=0),bounds[:,1].max(axis=0)])
        fallback=tuple(((full[0]+full[1])*.5)[[0,2]])
        reference,datum=REFERENCE.get(identity,(fallback,'water' if region=='manymouth_delta' and identity.rsplit('.',1)[1] in HAMLETS else 'terrain'))
        reference=np.asarray((references or {}).get(identity,reference),float)
        y=REFERENCE_HEIGHTS.get(identity,0. if datum=='water' else float(source_height(*reference)))
        footprints=[]
        if identity=='four_gates.civic':
            # Civic paving and the inhabited inner streets are one broad
            # terrace. Octagonal strips avoid a square imported terrain base.
            for z in range(-112,112,8):
                half=math.sqrt(max(0,112**2-(z+4)**2))
                footprints.append(np.array([[-half,z],[half,z+8]],float))
        for p,b in zip(members,bounds):
            # These three Manymouth banks are fitted to their actual upper
            # floors by manymouth_support. The old survey's rectangular
            # footing masks would restore trenches around the new bank edge.
            camp_member=identity=='amberwood.ridge-camp' and p['node'].startswith(('Prop_Tent_ridge_camp_','Brazier_ridge_camp_'))
            if (supports_ground(p) or camp_member) and identity not in D.REFERENCES:
                footprints.append(b[:,[0,2]]+np.array([[-1.5,-1.5],[1.5,1.5]]))
        result[identity]=Assembly(identity,tuple(p['node'] for p in members),reference,y,datum,full,tuple(footprints))
    return result


def apply_group_delta(objects, delta):
    """Reground an already placed assembly atomically, including its bounds."""
    delta=np.asarray(delta,float)
    if delta.shape!=(3,) or not np.isfinite(delta).all():raise ValueError('Assembly displacement must be finite XYZ')
    for obj in objects:
        for key in ('shift','low','high'):
            value=np.asarray(obj[key],float)
            value+=delta  # Preserve existing mapping/bounds array references.
            obj[key]=value
        if 'targetGround' in obj:obj['targetGround']+=float(delta[1])


def assert_rigid(objects, *, tolerance=1e-7):
    """Fail if a later placement/grounding pass tears an assembly apart."""
    shifts=np.array([obj['shift'] for obj in objects],float)
    if not np.isfinite(shifts).all():raise ValueError('Assembly displacement is not finite')
    if len(shifts) and np.max(np.abs(shifts-shifts[0]))>tolerance:
        raise ValueError('Connected assembly received independent component transforms')


def report(assembly):
    return {'id':assembly.id,'members':len(assembly.nodes),'nodes':list(assembly.nodes),
            'referenceXZ':assembly.reference_xz.tolist(),'referenceY':assembly.reference_y,
            'datum':assembly.datum,'sourceBounds':assembly.bounds.tolist(),
            'foundationFootprints':len(assembly.footprints),'geometryScale':1.,
            'placementPolicy':'One common translation; preserve all relative XYZ offsets and metadata.'}
