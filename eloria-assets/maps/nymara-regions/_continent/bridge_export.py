"""Export the UNION of river-crossing road surfaces in one global frame.

Independent outgoing/incoming road ribbons must never become separate decks
over the same channel. This exporter solves one common 1m height field, clips
its faces to a smooth road capsule union, and partitions it once by territory.
The sampled continent terrain is read-only. Failed bank fits are explicit.

Since the roads pass (R1) a deck is only a bridge: a claimed crossing site's
span plus landings of at most the plan's crossing_policy.deck_landing_metres,
or the same over deep water a road crosses away from any site (a sea channel).
Piers stand only under the span, over water. Floors are named per site
(Walk_ContinentalBridgeUnion_<site id + 1>_<territory>; decks away from a
site number from 500). Elevated walks that are not bridges belong to the
designed decks the plan names (landscape.designed_deck_entry).
"""
from __future__ import annotations

from pathlib import Path
import sys
import math
import io
from types import SimpleNamespace

import numpy as np
from scipy.ndimage import binary_dilation, label, find_objects
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import spsolve

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'_toolkit'))
import landscape as L
from world_layout import triangle_sample
from amberwood import gltf as G, mesh as M

CELL=1.
GRADE=.65
RETIRED_PLAN_KEYS=('bridge_approach_aprons','bridge_approach_connections')
TRIM_PASSES=6     # landing cells lifted over their bank beyond the deck lift limit are dropped and the deck solved again
SOLVE_GRADE=.64  # Margin for narrow clipped faces in float32 continent coordinates.
NEGLIGIBLE_FLOOR_AREA=1e-6  # square metres; a clipped outline below this is a sliver, not a floor
PRECISION_REMNANT_AREA=1e-4      # square metres: an encoded face failing the grade under this area is a remnant
PRECISION_REMNANT_ALTITUDE=.01   # metres: or thinner than this across its longest edge
CROSS=np.array([[0,1,0],[1,1,1],[0,1,0]],bool)
CAP_ARC_STEPS=12
POLYGON_EPS=1e-9


def _area_xz(polygon):
    x,z=polygon[:,0],polygon[:,2]
    # Shift before the shoelace sum to avoid cancellation at continent scale.
    x=x-x[0];z=z-z[0]
    return float(np.sum(x*np.roll(z,-1)-z*np.roll(x,-1))*.5)


def _clip_halfplane(polygon,a,b,inside=True):
    """Clip XYZ while preserving its original deck triangle plane."""
    edge=b-a
    distance=edge[0]*(polygon[:,2]-a[1])-edge[1]*(polygon[:,0]-a[0])
    if not inside:distance=-distance
    keep=distance>=-POLYGON_EPS
    if keep.all():return polygon
    if not keep.any():return np.empty((0,3))
    output=[]
    for i in range(len(polygon)):
        j=(i-1)%len(polygon)
        if keep[i]!=keep[j]:
            t=distance[j]/(distance[j]-distance[i])
            output.append(polygon[j]+t*(polygon[i]-polygon[j]))
        if keep[i]:output.append(polygon[i])
    result=np.asarray(output)
    # Coincident vertices are common where neighbouring capsules overlap.
    distinct=np.linalg.norm(result-np.roll(result,1,axis=0),axis=1)>1e-8
    result=result[distinct]
    return result if len(result)>=3 and abs(_area_xz(result))>1e-10 else np.empty((0,3))


class RoadOutline:
    """Deterministic convex-capsule union, without a geometry dependency.

    Each cap is inscribed with a maximum 15-degree angular step. The greatest
    inset is <0.009 times the road half-width (about 3cm on a normal road).
    Subtracting previously covered convex pieces prevents overlapping faces.
    """
    bin_size=8.

    def __init__(self,world):
        unique=set()
        for road in world.roads:
            points=np.asarray(road['points'],float)[:,[0,2]]
            for a,b in zip(points,points[1:]):
                if np.linalg.norm(b-a)<1e-8:continue
                a,b=sorted((tuple(a),tuple(b)))
                unique.add((*a,*b,float(road['width'])))
        self.segments=np.asarray(sorted(unique),float).reshape(-1,5)
        self.polygons=[];self.bins={}
        for index,(ax,az,bx,bz,width) in enumerate(self.segments):
            angle=math.atan2(bz-az,bx-ax)
            arc=angle+np.linspace(-math.pi*.5,math.pi*.5,CAP_ARC_STEPS+1)
            polygon=np.concatenate((np.c_[bx+width*np.cos(arc),bz+width*np.sin(arc)],
                                    np.c_[ax-width*np.cos(arc),az-width*np.sin(arc)]))
            self.polygons.append(polygon)
            low=np.floor(polygon.min(axis=0)/self.bin_size).astype(int)
            high=np.floor(polygon.max(axis=0)/self.bin_size).astype(int)
            for x in range(low[0],high[0]+1):
                for z in range(low[1],high[1]+1):self.bins.setdefault((x,z),[]).append(index)

    def candidates(self,low,high=None):
        low=np.floor(np.asarray(low)/self.bin_size).astype(int)
        high=low if high is None else np.floor(np.asarray(high)/self.bin_size).astype(int)
        return sorted({i for x in range(low[0],high[0]+1) for z in range(low[1],high[1]+1)
                       for i in self.bins.get((x,z),())})

    @staticmethod
    def inside(polygon,points,tolerance=0.):
        a=polygon;b=np.roll(polygon,-1,axis=0);d=b-a
        distance=d[:,0]*(points[...,1,None]-a[:,1])-d[:,1]*(points[...,0,None]-a[:,0])
        return np.all(distance>=-(POLYGON_EPS+tolerance*np.linalg.norm(d,axis=1)),axis=-1)

    def contains(self,x,z,tolerance=0.):
        x,z=np.broadcast_arrays(np.asarray(x,float),np.asarray(z,float));shape=x.shape
        points=np.c_[x.ravel(),z.ravel()];result=np.zeros(len(points),bool)
        if not len(points):return result.reshape(shape)
        bins=np.floor(points/self.bin_size).astype(int)
        keys,inverse=np.unique(bins,axis=0,return_inverse=True)
        for group,key in enumerate(keys):
            members=np.flatnonzero(inverse==group)
            for index in self.bins.get(tuple(key),()):
                remaining=members[~result[members]]
                if not len(remaining):break
                result[remaining]|=self.inside(self.polygons[index],points[remaining],tolerance)
        return result.reshape(shape)

    def clip(self,triangle):
        candidates=self.candidates(triangle[:,[0,2]].min(axis=0),triangle[:,[0,2]].max(axis=0))
        # Almost every interior triangle fits inside one capsule unchanged.
        for index in candidates:
            if self.inside(self.polygons[index],triangle[:,[0,2]]).all():return [triangle]
        uncovered=[triangle];covered=[]
        for index in candidates:
            capsule=self.polygons[index];remaining=[]
            for piece in uncovered:
                inside=piece
                for a,b in zip(capsule,np.roll(capsule,-1,axis=0)):
                    outside=_clip_halfplane(inside,a,b,False)
                    if len(outside):remaining.append(outside)
                    inside=_clip_halfplane(inside,a,b)
                    if not len(inside):break
                if len(inside):covered.append(inside)
            uncovered=remaining
            if not uncovered:break
        return self._outer_loops(covered,triangle,candidates)

    def _outer_loops(self,pieces,triangle,candidates):
        """Remove internal Boolean cuts before triangulating the deck.

        Overlapping end caps often leave almost coincident internal slivers.
        They have no effect on the outline, but separate float32 triangles
        would turn them into steep or degenerate collision faces.
        """
        if len(pieces)<2:return pieces
        edges=np.concatenate([np.stack((p,np.roll(p,-1,axis=0)),axis=1) for p in pieces])
        a,b=edges[:,0],edges[:,1];delta=(b-a)[:,[0,2]]
        lengths=np.linalg.norm(delta,axis=1)
        outward=np.c_[-delta[:,1],delta[:,0]]/np.maximum(lengths[:,None],1e-20)
        sample=(a+b)[:,[0,2]]*.5+outward*1e-6
        inside_triangle=self.inside(triangle[::-1][:,[0,2]],sample)
        inside_union=np.zeros(len(sample),bool)
        for index in candidates:
            remaining=np.flatnonzero(inside_triangle&~inside_union)
            if not len(remaining):break
            inside_union[remaining]|=self.inside(self.polygons[index],sample[remaining])
        boundary=edges[~(inside_triangle&inside_union)&(lengths>1e-8)]
        if not len(boundary):return pieces
        vertices,index=np.unique(np.round(boundary.reshape(-1,3),7),axis=0,return_inverse=True)
        links=index.reshape(-1,2)
        if len(np.unique(links[:,0]))!=len(links) or len(np.unique(links[:,1]))!=len(links):return pieces
        next_vertex=dict(links);loops=[]
        while next_vertex:
            first=min(next_vertex);current=first;loop=[]
            for _ in range(len(next_vertex)+1):
                loop.append(current)
                if current not in next_vertex:return pieces
                current=next_vertex.pop(current)
                if current==first:break
            else:return pieces
            polygon=vertices[loop]
            if len(polygon)<3 or _area_xz(polygon)>=0:return pieces  # Retain exact pieces if there is a hole.
            loops.append(polygon)
        return loops


def precision_remnants(faces,areas):
    """Faces too small or too thin to carry a floor grade: area under a square centimetre, or altitude under a centimetre."""
    xz=np.asarray(faces)[:,:,[0,2]]
    longest=np.max(np.linalg.norm(np.roll(xz,-1,axis=1)-xz,axis=2),axis=1)
    altitude=2*np.asarray(areas)/np.maximum(longest,1e-12)
    return (np.asarray(areas)<PRECISION_REMNANT_AREA)|(altitude<PRECISION_REMNANT_ALTITUDE)


def triangulate_floor(polygon):
    """Stable ear clipping of a clockwise, possibly concave floor outline."""
    polygon=np.asarray(polygon)
    # A deck cell clipped at a tangent of the road outline can leave a sliver
    # a tenth of a millimetre across (float32 at continent coordinates): no
    # floor at all, not a failure.
    if len(polygon)<3 or abs(_area_xz(polygon))<NEGLIGIBLE_FLOOR_AREA:return []
    # Collapse redundant outside-boundary vertices at sub-millimetre scale.
    # This is below GLB precision at continent coordinates, not an art change.
    changed=True
    while changed and len(polygon)>3:
        changed=False
        for i in range(len(polygon)):
            a,b,c=polygon[[i-1,i,(i+1)%len(polygon)],:][:,[0,2]]
            chord=c-a;length=np.linalg.norm(chord)
            distance=abs(chord[0]*(b[1]-a[1])-chord[1]*(b[0]-a[0]))/max(length,1e-20)
            if (np.linalg.norm(b-a)<1e-5 or
                    (distance<1e-6 and np.dot(b-a,c-b)>=0)):
                polygon=np.delete(polygon,i,axis=0);changed=True;break
    indices=list(range(len(polygon)));result=[]
    while len(indices)>3:
        best=None;best_score=-1.
        for i in range(len(indices)):
            ids=[indices[i-1],indices[i],indices[(i+1)%len(indices)]]
            face=polygon[ids];area=-_area_xz(face)
            if area<1e-12:continue
            other=[j for j in indices if j not in ids]
            if other and RoadOutline.inside(face[::-1][:,[0,2]],polygon[other][:,[0,2]]).any():continue
            longest=max(np.linalg.norm(face[1,[0,2]]-face[0,[0,2]]),np.linalg.norm(face[2,[0,2]]-face[1,[0,2]]),
                        np.linalg.norm(face[0,[0,2]]-face[2,[0,2]]))
            score=area/max(longest,1e-20)
            if score>best_score:best=i;best_score=score
        if best is None:
            raise ValueError('Clipped bridge outline could not be triangulated')
        ids=[indices[best-1],indices[best],indices[(best+1)%len(indices)]]
        result.append(polygon[ids]);indices.pop(best)
    if len(indices)==3:result.append(polygon[indices])
    return result


def vertices_for_cells(mask):
    result=np.zeros((mask.shape[0]+1,mask.shape[1]+1),bool)
    result[:-1,:-1]|=mask;result[:-1,1:]|=mask
    result[1:,:-1]|=mask;result[1:,1:]|=mask
    return result


def bounded_floor(lower,active,maximum_grade=SOLVE_GRADE):
    """Smallest majorant with axis slopes <= grade/sqrt(2).

    Each grid triangle then has Euclidean slope <= grade. Max propagation
    preserves all terrain/water lower bounds and cannot create a folded face.
    """
    if not 0<maximum_grade<=GRADE:raise ValueError('Bridge grade must be in (0,.65]')
    if not np.isfinite(np.asarray(lower)[active]).all():raise ValueError('Non-finite bridge lower bound')
    value=np.where(active,lower,-np.inf).astype(float)
    step=maximum_grade/math.sqrt(2)*CELL
    for _ in range(active.size+1):
        new=value.copy()
        new[1:]=np.maximum(new[1:],value[:-1]-step)
        new[:-1]=np.maximum(new[:-1],value[1:]-step)
        new[:,1:]=np.maximum(new[:,1:],value[:,:-1]-step)
        new[:,:-1]=np.maximum(new[:,:-1],value[:,1:]-step)
        new[~active]=-np.inf
        if np.max(new[active]-value[active],initial=0)<1e-9:return new
        value=new
    raise ValueError('Common bridge profile did not converge')


def bank_profile(lower,active,water):
    """Harmonic bank-to-bank grade, held above the water-clearance floor."""
    unknown=active&water;fixed=active&~unknown
    if not unknown.any():return lower.copy()
    if not fixed.any():raise ValueError('A continental bridge requires an actual dry bank')
    index=np.full(active.shape,-1,int);index[unknown]=np.arange(int(unknown.sum()))
    rows,cols=np.nonzero(unknown);matrix_rows=[];matrix_cols=[];values=[]
    rhs=np.zeros(len(rows));degree=np.zeros(len(rows))
    for dz,dx in ((0,-1),(0,1),(-1,0),(1,0)):
        nz,nx=rows+dz,cols+dx
        valid=(nz>=0)&(nx>=0)&(nz<active.shape[0])&(nx<active.shape[1])
        current=np.flatnonzero(valid);nz=nz[valid];nx=nx[valid]
        valid=active[nz,nx];current=current[valid];nz=nz[valid];nx=nx[valid]
        degree[current]+=1
        neighbor=index[nz,nx];known=neighbor<0
        rhs[current[known]]+=lower[nz[known],nx[known]]
        matrix_rows.extend(current[~known]);matrix_cols.extend(neighbor[~known]);values.extend([-1.]*int((~known).sum()))
    matrix_rows.extend(range(len(rows)));matrix_cols.extend(range(len(rows)));values.extend(degree)
    matrix=coo_matrix((values,(matrix_rows,matrix_cols)),shape=(len(rows),len(rows))).tocsc()
    solved=spsolve(matrix,rhs)
    if not np.isfinite(solved).all():raise ValueError('Bridge bank profile is not connected to dry ground')
    result=lower.copy();result[unknown]=np.maximum(lower[unknown],solved)
    return result


def road_footprint(world):
    """Conservative grid for the later exact capsule clip.

    Testing only cell centres cuts diagonal shoulders off before clipping.
    Half a cell diagonal keeps every cell touched by the true road outline.
    """
    nx=int(round((world.x1-world.x0)/CELL));nz=int(round((world.z1-world.z0)/CELL))
    mask=np.zeros((nz,nx),bool)
    for road in world.roads:
        points=np.asarray(road['points'],float)[:,[0,2]];width=float(road['width'])+CELL/math.sqrt(2)
        for a,b in zip(points,points[1:]):
            low=np.minimum(a,b)-width;high=np.maximum(a,b)+width
            ix0=max(0,int(np.floor((low[0]-world.x0)/CELL)));ix1=min(nx,int(np.ceil((high[0]-world.x0)/CELL)))
            iz0=max(0,int(np.floor((low[1]-world.z0)/CELL)));iz1=min(nz,int(np.ceil((high[1]-world.z0)/CELL)))
            if ix0>=ix1 or iz0>=iz1:continue
            x,z=np.meshgrid(world.x0+(np.arange(ix0,ix1)+.5)*CELL,world.z0+(np.arange(iz0,iz1)+.5)*CELL)
            dx,dz=b-a;length=dx*dx+dz*dz
            if length<1e-12:continue
            t=np.clip(((x-a[0])*dx+(z-a[1])*dz)/length,0,1)
            mask[iz0:iz1,ix0:ix1]|=np.hypot(x-a[0]-t*dx,z-a[1]-t*dz)<=width
    return mask


def frontier_vertices(cells,road):
    """Vertices where a bridge joins the continuing dry road footprint."""
    result=np.zeros((cells.shape[0]+1,cells.shape[1]+1),bool)
    outside=road&~cells
    across=(cells[:,:-1]&outside[:,1:])|(outside[:,:-1]&cells[:,1:])
    result[:-1,1:-1]|=across;result[1:,1:-1]|=across
    across=(cells[:-1]&outside[1:])|(outside[:-1]&cells[1:])
    result[1:-1,:-1]|=across;result[1:-1,1:]|=across
    return result


def deck_policy(world):
    """(landing metres, lift metres) of the plan's crossing policy (landscape defaults without a plan)."""
    plan=getattr(world,'plan',None) or {}
    for key in RETIRED_PLAN_KEYS:
        if key in plan:
            raise ValueError(f'{key}: retired by the roads pass (R1): a bridge deck is its site span plus landings of at most '
                             'crossing_policy.deck_landing_metres; remove the key from diagonal-plan.json')
    policy=L.crossing_policy(plan)
    return float(policy['deck_landing_metres']),float(policy['deck_lift_metres'])


def site_span_cells(world,site,road,landing):
    """Road footprint cells on a crossing site's span: along its axis from landing metres before the first wet edge
    to landing metres beyond the last, and across it within the widest road plus a cell."""
    left,right=np.asarray(site['wetEdges'][0],float),np.asarray(site['wetEdges'][1],float)
    axis=right-left;length=float(np.linalg.norm(axis))
    if length<1e-9:return np.zeros_like(road)
    axis/=length;across=np.array([-axis[1],axis[0]])
    half=max((float(r['width']) for r in world.roads),default=4.)+CELL
    start=left-axis*landing;span=length+2*landing
    corners=np.array([start+across*half,start-across*half,start+axis*span+across*half,start+axis*span-across*half])
    lo=np.floor((corners.min(axis=0)-[world.x0,world.z0])/CELL).astype(int);hi=np.ceil((corners.max(axis=0)-[world.x0,world.z0])/CELL).astype(int)
    ix0,iz0=max(0,lo[0]),max(0,lo[1]);ix1,iz1=min(road.shape[1],hi[0]+1),min(road.shape[0],hi[1]+1)
    cells=np.zeros_like(road)
    if ix0>=ix1 or iz0>=iz1:return cells
    x,z=np.meshgrid(world.x0+(np.arange(ix0,ix1)+.5)*CELL,world.z0+(np.arange(iz0,iz1)+.5)*CELL)
    along=(x-start[0])*axis[0]+(z-start[1])*axis[1];side=(x-start[0])*across[0]+(z-start[1])*across[1]
    cells[iz0:iz1,ix0:ix1]=(along>=0)&(along<=span)&(np.abs(side)<=half)
    return cells&road


def landing_cut(mask,cut,dry_cells):
    """The cells one landing trim removes from a deck: its lifted cells and every cell they part from the water.

    A landing ends at its first lifted cell. Cells beyond it that no longer share a cell edge, through the rest of
    the deck, with a cell over the water (one with a vertex that is not dry) would stand as a floor of their own,
    joined to the span through a cell corner at most, which nobody walks: they go with the cut, so a trim never
    leaves a deck in pieces. ``mask``, ``cut`` and ``dry_cells`` are the component's cell grids.
    """
    kept=mask&~cut
    parts,_=label(kept,structure=CROSS)
    wet=np.unique(parts[kept&~dry_cells])
    return mask&~np.isin(parts,wet[wet>0])


def common_surface(world, *, water_fields=None, maximum_extension=None):
    """One deck field over every bridge the roads need, clipped later to the road capsule union.

    A bridge deck is a crossing site's span (river_crossings: the wet width at a claimed site) plus landings of at
    most ``crossing_policy.deck_landing_metres`` on each bank, over the road cells there; deep water a road crosses
    anywhere else (a sea channel between islands) gets the same deck: its wet cells plus that landing. Nothing else
    is decked: the approach aprons, the connection aprons, the bank growth and the floating-run spans of earlier
    publications are retired (``maximum_extension`` is accepted and ignored). A deck stands on the water clearance,
    the harmonic bank-to-bank grade over water and the bounded-grade majorant; over dry ground it rests 2.5 cm above
    the bed, and wherever the grade majorant lifts it further, or a landing cannot meet its bank within the grade,
    the report says so instead of growing the deck.
    """
    water_fields=water_fields or L.water_fields
    landing,lift_limit=deck_policy(world)
    outline=RoadOutline(world)
    road=road_footprint(world);rows,cols=np.nonzero(road)
    x=world.x0+(cols+.5)*CELL;z=world.z0+(rows+.5)*CELL
    ground=world.height_at(x,z)
    water=water_fields(x,z,height=ground,plan=world.plan)
    # Conservative shoulder cells must not invent a bridge on a dry road
    # merely because nearby water reaches an invisible grid-cell centre.
    inside=outline.contains(x,z)
    wet=np.zeros_like(road);wet[rows,cols]=water['mask']&(water['depth']>.35)&inside
    river=np.zeros_like(road)
    if 'river_mask' in water:river[rows,cols]=np.asarray(water['river_mask'],bool)&inside
    sites=[site for site in getattr(world,'crossing_sites',[]) if getattr(world,'crossing_site_roads',{}).get(site['id'],True)]
    site_cells={};spanned=np.zeros_like(road)
    for site in sites:
        cells=site_span_cells(world,site,road,landing)
        if cells.any():site_cells[site['id']]=cells;spanned|=cells
    # Deep water a road crosses away from every site: its own wet cells plus the landing.
    loose=wet&~spanned
    cells=loose.copy()
    for _ in range(int(math.ceil(landing/CELL))):cells=binary_dilation(cells,structure=CROSS)&road
    cells|=spanned
    stray_river=river&wet&~spanned
    final=np.full((road.shape[0]+1,road.shape[1]+1),np.nan)
    # A deck lifts at most deck_lift_metres over dry ground: a landing cell the solved deck would carry higher over
    # its bank is left to the graded road, and the deck is solved again without it (a steep bank ends the landing,
    # and the landing cells beyond it go too: landing_cut).
    trimmed=0;cut_off=0;cut_banks=[]
    for attempt in range(TRIM_PASSES+1):
        final.fill(np.nan)
        labels,count=label(cells,structure=np.ones((3,3)))
        frontier=frontier_vertices(cells,road)
        components=[];maximum_bank_error=0.;worst_bank=None;lift_reports=[];next_loose=500;trim=np.zeros_like(cells)
        for component,sl in enumerate(find_objects(labels),1):
            if sl is None:continue
            iz0,iz1=sl[0].start,sl[0].stop;ix0,ix1=sl[1].start,sl[1].stop
            mask=labels[sl]==component;active=vertices_for_cells(mask)
            gx,gz=np.meshgrid(world.x0+np.arange(ix0,ix1+1)*CELL,world.z0+np.arange(iz0,iz1+1)*CELL)
            bed=world.height_at(gx,gz)
            wf=water_fields(gx,gz,height=bed,plan=world.plan)
            water_vertices=wf['mask']&(wf['depth']>.35)
            lower=np.where(water_vertices,np.maximum(bed+.025,wf['surface']+.85),bed+.025)
            deck=bounded_floor(bank_profile(lower,active,water_vertices),active)
            dry=active&~wf['mask']
            lifted=dry&(deck-bed>lift_limit+1e-9)
            if lifted.any() and attempt<TRIM_PASSES:
                corners=dry[:-1,:-1]&dry[1:,:-1]&dry[:-1,1:]&dry[1:,1:]
                touching=lifted[:-1,:-1]|lifted[1:,:-1]|lifted[:-1,1:]|lifted[1:,1:]
                cut=mask&corners&touching
                if cut.any() and (mask&~cut&~corners).any():
                    removed=landing_cut(mask,cut,corners)
                    view=trim[sl];view|=removed
                    beyond=removed&~cut
                    if beyond.any():
                        cut_off+=int(beyond.sum())
                        rr,cc=np.nonzero(cut&binary_dilation(beyond,structure=CROSS))
                        if len(rr):cut_banks.append([round(float(world.x0+(ix0+cc.mean()+.5)*CELL),1),round(float(world.z0+(iz0+rr.mean()+.5)*CELL),1)])
            bank=frontier[iz0:iz1+1,ix0:ix1+1]&active
            error=float(np.max(deck[bank]-bed[bank],initial=0))
            if bank.any() and error>=maximum_bank_error:
                worst=int(np.argmax(np.where(bank,deck-bed,-np.inf)))
                worst_bank=(float(gx.ravel()[worst]),float(gz.ravel()[worst]))
            maximum_bank_error=max(maximum_bank_error,error)
            members=sorted(site_id for site_id,site_mask in site_cells.items() if (site_mask[sl]&mask).any())
            identity=members[0]+1 if members else next_loose
            if not members:next_loose+=1
            report={'component':identity,'sites':members,'cells':int(mask.sum()),'bankErrorMetres':round(error,3),
                    'dryLiftOverLimitVertices':int(lifted.sum()),'maximumDryLiftMetres':round(float(np.max((deck-bed)[dry],initial=0)),3)}
            if lifted.any():
                where=int(np.argmax(np.where(lifted,deck-bed,-np.inf)))
                report['worstDryLift']=[round(float(gx.ravel()[where]),1),round(float(gz.ravel()[where]),1)]
            lift_reports.append(report)
            view=final[iz0:iz1+1,ix0:ix1+1];view[active]=deck[active]
            components.append({'id':identity,'sites':members,'slice':sl,'cells':mask,'height':deck,'bankError':error,
                               'water':water_vertices})
        if not trim.any():break
        cells=cells&~trim;trimmed+=int(trim.sum())
    for component in components:component['outline']=outline
    stray=[]
    if stray_river.any():
        zs,xs=np.nonzero(stray_river)
        stray=[[round(float(world.x0+(c+.5)*CELL),1),round(float(world.z0+(r+.5)*CELL),1)] for r,c in list(zip(zs,xs))[::25]]
    return {'x0':world.x0,'z0':world.z0,'cell':CELL,'mask':cells,'height':final,'components':components,'outline':outline,
            'wetCells':int(wet.sum()),'siteCells':int(spanned.sum()),'looseWetCells':int(loose.sum()),
            'riverWaterOutsideSites':{'cells':int(stray_river.sum()),'at':stray},
            'maximumBankError':maximum_bank_error,'worstBank':worst_bank,'deckLandingMetres':landing,'deckLiftMetres':lift_limit,
            'trimmedLandingCells':trimmed,'cutOffLandingCells':cut_off,'cutOffLandingBanks':cut_banks,'decks':lift_reports}



def surface_at(world,x,z,field=None):
    """Exact same grid diagonal as emitted decks, including shared edges."""
    field=field if field is not None else world.bridge_field
    x,z=np.broadcast_arrays(np.asarray(x,float),np.asarray(z,float))
    result=np.asarray(world.height_at(x,z),float).copy()
    fx=(x-field['x0'])/CELL;fz=(z-field['z0'])/CELL
    base_x=np.floor(fx).astype(int);base_z=np.floor(fz).astype(int)
    mask=field['mask'];h=field['height']
    # A visible GLB contour vertex can round a few ten-thousandths of a metre
    # across its analytic boundary. Keep lookup on that same encoded floor.
    inside=field['outline'].contains(x,z,tolerance=2e-4) if 'outline' in field else True
    for dx,dz in ((0,0),(-1,0),(0,-1),(-1,-1)):
        ix,iz=base_x+dx,base_z+dz;u,v=fx-ix,fz-iz
        valid=(ix>=0)&(iz>=0)&(ix<mask.shape[1])&(iz<mask.shape[0])&(u>=0)&(u<=1)&(v>=0)&(v<=1)
        cx=np.clip(ix,0,mask.shape[1]-1);cz=np.clip(iz,0,mask.shape[0]-1)
        valid&=mask[cz,cx]&inside
        a,b,c,d=h[cz,cx],h[cz,cx+1],h[cz+1,cx],h[cz+1,cx+1]
        y=np.where(u+v<=1,a+(b-a)*u+(c-a)*v,d+(c-d)*(1-u)+(b-d)*(1-v))
        result=np.where(valid,np.maximum(result,y),result)
    return result


def encoded_floor_vertices(world,component,xz):
    """Encode XZ first, then lift that exact point onto the common floor.

    Independent XYZ rounding changes the grade of a thin clipped face. One
    shared height for every encoded XZ also keeps neighbouring source planes
    joined when rounding moves an outline intersection across their diagonal.
    """
    xz=np.asarray(xz,dtype=np.float32).astype(float)
    sl=component['slice'];mask=component['cells'];h=component['height']
    fx=(xz[:,0]-world.x0)/CELL-sl[1].start
    fz=(xz[:,1]-world.z0)/CELL-sl[0].start
    bx,bz=np.floor(fx).astype(int),np.floor(fz).astype(int)
    y=np.full(len(xz),np.nan)
    for dx,dz in ((0,0),(-1,0),(0,-1),(-1,-1)):
        ix,iz=bx+dx,bz+dz;u,v=fx-ix,fz-iz
        valid=(ix>=0)&(iz>=0)&(ix<mask.shape[1])&(iz<mask.shape[0])&(u>=0)&(u<=1)&(v>=0)&(v<=1)
        cx=np.clip(ix,0,mask.shape[1]-1);cz=np.clip(iz,0,mask.shape[0]-1)
        valid&=mask[cz,cx]&~np.isfinite(y)
        selected=np.flatnonzero(valid)
        cx,cz,u,v=cx[selected],cz[selected],u[selected],v[selected]
        a,b,c,d=h[cz,cx],h[cz,cx+1],h[cz+1,cx],h[cz+1,cx+1]
        y[selected]=np.where(u+v<=1,a+(b-a)*u+(c-a)*v,d+(c-d)*(1-u)+(b-d)*(1-v))
    if not np.isfinite(y).all():raise ValueError('Encoded bridge outline left its common support floor')
    return np.c_[xz[:,0],y.astype(np.float32).astype(float),xz[:,1]]


def deck_mesh(world,component):
    sl=component['slice'];mask=component['cells'];heights=component['height']
    gx,gz=np.meshgrid(world.x0+np.arange(sl[1].start,sl[1].stop+1)*CELL,
                      world.z0+np.arange(sl[0].start,sl[0].stop+1)*CELL)
    row,col=np.nonzero(mask);a=row*gx.shape[1]+col;b=a+1;c=a+gx.shape[1];d=c+1
    indices=np.c_[a,c,b,b,c,d].reshape(-1,3)
    vertices=np.c_[gx.ravel(),heights.ravel(),gz.ravel()]
    centers=np.c_[world.x0+(sl[1].start+col+.5)*CELL,world.z0+(sl[0].start+row+.5)*CELL]
    owners=np.repeat(world.owner_at(centers[:,0],centers[:,1]).astype(int),2)
    outline=component.get('outline') or RoadOutline(world)
    triangles=[];clipped_owners=[];areas=[]
    for triangle,owner in zip(vertices[indices],owners):
        for polygon in outline.clip(triangle):
            for face in triangulate_floor(polygon):
                area=abs(_area_xz(face))
                if area<1e-8:continue
                triangles.append(face);clipped_owners.append(owner);areas.append(area)
    if not triangles:raise ValueError('Bridge component has no road-width deck')
    xz,remap=np.unique(np.asarray(triangles)[:,:,[0,2]].reshape(-1,2).astype(np.float32),axis=0,return_inverse=True)
    positions=encoded_floor_vertices(world,component,xz)
    faces=positions[remap.reshape(-1,3)]
    normal=np.cross(faces[:,1]-faces[:,0],faces[:,2]-faces[:,0])
    invalid=(normal[:,1]<=0)|(np.hypot(normal[:,0],normal[:,2])>GRADE*normal[:,1])
    # Only remnants can fail as encoded floor faces: a face under a square
    # centimetre, or one thinner than a centimetre across its longest edge (a
    # clipped sliver a metre long and a quarter of a millimetre wide lying
    # across the crease between two bounded grid triangles takes the crease's
    # grade). Nothing walks either and the served grid never samples them.
    # This is no exemption for a narrow ordinary face: every retained encoded
    # face still receives the strict grade, winding and non-degeneracy check
    # in build_bridges.
    cleanup=invalid&precision_remnants(faces,np.asarray(areas))
    component['precisionCleanupArea']=float(np.sum(np.asarray(areas)[cleanup]))
    remap=remap.reshape(-1,3)[~cleanup]
    clipped_owners=np.asarray(clipped_owners)[~cleanup]
    used,reindexed=np.unique(remap,return_inverse=True)
    positions=positions[used];remap=reindexed.reshape(-1,3)
    mesh=M.Mesh(positions=positions,normals=np.tile([0.,1.,0.],(len(positions),1)),
        uvs=positions[:,[0,2]]*.25,indices=remap.ravel(),material='bridge_timber')
    mesh.recompute_normals(180)
    return mesh,clipped_owners


def edge_fascia(mesh,owners,outline):
    """Shallow outside timber faces below the floor, never across a bank join.

    Test the capsule exterior instead of counting unmatched edges: union clips
    can have harmless collinear T-junctions inside a common surface.
    """
    faces=mesh.indices.reshape(-1,3)
    edges=np.concatenate([faces[:,[i,(i+1)%3]] for i in range(3)])
    edge_owners=np.tile(owners,3)
    unique,index,count=np.unique(np.sort(edges,axis=1),axis=0,return_index=True,return_counts=True)
    boundary=edges[index[count==1]];edge_owners=edge_owners[index[count==1]]
    a,b=mesh.positions[boundary[:,0]],mesh.positions[boundary[:,1]]
    dxz=(b-a)[:,[0,2]];length=np.linalg.norm(dxz,axis=1)
    normal=np.c_[-dxz[:,1],dxz[:,0]]/np.maximum(length[:,None],1e-12)
    middle=(a+b)[:,[0,2]]*.5;outside=middle+normal*1e-5;inside=middle-normal*1e-5
    keep=(length>1e-4)&~outline.contains(outside[:,0],outside[:,1])&outline.contains(inside[:,0],inside[:,1])
    a,b=a[keep],b[keep];edge_owners=edge_owners[keep]
    if not len(a):return None,np.empty(0,int)
    bottom_a=a-np.array([0,.32,0]);bottom_b=b-np.array([0,.32,0])
    positions=np.stack((a,b,bottom_a,bottom_b),axis=1).reshape(-1,3)
    indices=(np.arange(len(a))[:,None]*4+np.array([0,2,1,1,2,3])).ravel()
    fascia=M.Mesh(positions=positions,normals=np.zeros_like(positions),uvs=positions[:,[0,2]]*.25,
                  indices=indices,material='bridge_edge_timber')
    fascia.recompute_normals(180)
    return fascia,np.repeat(edge_owners,2)


def timber_texture():
    """A small, deliberately broad plank pattern readable from the camera."""
    from PIL import Image
    x,y=np.meshgrid(np.arange(128),np.arange(128));plank=y//16
    tones=np.array([0,-5,3,-2,4,-3,2,-4])[plank]
    grain=2*np.sin(x*.19+plank*1.7)+np.sin(x*.53+y*.22)
    seam=(y%16<1)|((x+(plank%2)*64)%128<1)
    rgb=np.stack([103+tones+grain,83+tones+grain,61+tones+grain],axis=-1)
    rgb[seam]=[56,44,32]
    output=io.BytesIO();Image.fromarray(np.uint8(np.clip(rgb,0,255))).save(output,format='PNG')
    return output.getvalue()


def merge_meshes(meshes):
    """One mesh of several of one material (a site's disconnected deck pieces, their fascias)."""
    if len(meshes)==1:return meshes[0]
    offsets=np.cumsum([0]+[len(m.positions) for m in meshes[:-1]])
    return M.Mesh(positions=np.concatenate([m.positions for m in meshes]),normals=np.concatenate([m.normals for m in meshes]),
                  uvs=np.concatenate([m.uvs for m in meshes]),indices=np.concatenate([m.indices+o for m,o in zip(meshes,offsets)]),
                  material=meshes[0].material)


def subset_mesh(mesh,triangles):
    indices=mesh.indices.reshape(-1,3)[triangles]
    used,remap=np.unique(indices,return_inverse=True)
    return M.Mesh(positions=mesh.positions[used],normals=mesh.normals[used],uvs=mesh.uvs[used],
                  indices=remap.ravel(),material=mesh.material)


def pier_floor_minimum(faces,x,z,width=.8):
    """Minimum actual encoded deck over the complete encoded pier footprint.

    Clip every intersecting emitted floor triangle, preserving its plane. The
    minimum may occur at a triangle/grid boundary inside the footprint rather
    than its corners. A partial shoulder cannot support a full-width pier.
    """
    low=np.asarray([x-width*.5,z-width*.5],dtype=np.float32).astype(float)
    high=np.asarray([x+width*.5,z+width*.5],dtype=np.float32).astype(float)
    rectangle=np.array([low,[high[0],low[1]],high,[low[0],high[1]]])
    xz=faces[:,:,[0,2]]
    candidates=faces[np.all(xz.max(axis=1)>=low,axis=1)&np.all(xz.min(axis=1)<=high,axis=1)]
    area=0.;minimum=np.inf
    for triangle in candidates:
        polygon=triangle
        for a,b in zip(rectangle,np.roll(rectangle,-1,axis=0)):
            polygon=_clip_halfplane(polygon,a,b)
            if not len(polygon):break
        if len(polygon):
            area+=abs(_area_xz(polygon));minimum=min(minimum,float(polygon[:,1].min()))
    footprint=float(np.prod(high-low))
    if not np.isfinite(minimum) or abs(area-footprint)>max(1e-6,footprint*1e-6):return None
    return minimum


def pier_mesh(world,faces,x,z):
    minimum=pier_floor_minimum(faces,x,z)
    if minimum is None:return None
    # Downward float32 rounding bounds the encoded cap as well as its centre.
    top=float(np.nextafter(np.float32(minimum-.12),np.float32(-np.inf)))
    bed=float(world.height_at(x,z))
    if top-bed<.4:return None
    height=top-bed+.06
    return M.box((.8,height,.8),center=(x,bed-.06+height*.5,z),material='bridge_stone')


def fit_pier(world,faces,x,z):
    """Fit an edge support inward without changing its planned bridge span."""
    offsets=[(0.,0.)]+sorted(((dx*.2,dz*.2) for dx in range(-6,7) for dz in range(-6,7)
        if 0<dx*dx+dz*dz<=36),key=lambda q:(q[0]*q[0]+q[1]*q[1],q[0],q[1]))
    for dx,dz in offsets:
        minimum=pier_floor_minimum(faces,x+dx,z+dz)
        if minimum is None:continue
        mesh=pier_mesh(world,faces,x+dx,z+dz)
        return mesh,{'planned':[x,z],'position':[x+dx,z+dz],'shiftMetres':math.hypot(dx,dz),
            'minimumDeck':minimum,'status':'supported' if mesh is not None else 'grounded bank stub'}
    raise ValueError(f'Bridge pier at {x},{z} has no complete .8m deck footprint within1.2m')


def support_spacing(world,faces,planned,placed):
    """Comparable geometric span estimate over emitted floor samples.

    Grounded deck points act as bank supports. Twice the largest nearest-anchor
    distance estimates unsupported spacing; it is not a structural beam model.
    """
    from scipy.spatial import cKDTree
    samples=np.unique(np.r_[faces.reshape(-1,3),faces.mean(axis=1)],axis=0)
    ground=np.asarray(world.height_at(samples[:,0],samples[:,2]))
    banks=samples[samples[:,1]-ground<=.4][:,[0,2]]
    suspended=samples[samples[:,1]-ground>.4][:,[0,2]]
    def span(points):
        if not len(suspended):return 0.
        anchors=np.r_[np.asarray(points).reshape(-1,2),banks]
        return float(cKDTree(anchors).query(suspended)[0].max()*2) if len(anchors) else None
    return {'supportsBefore':len(planned),'supportsAfter':len(placed),
        'oldMaximumUnsupportedSpanEstimateMetres':span(planned),
        'maximumUnsupportedSpanEstimateMetres':span(placed),
        'spanMetric':'Twice maximum nearest-support/bank distance at emitted vertices and triangle centres; geometric spacing estimate'}


def build_bridges(world,path, *, water_fields=None):
    """Return bridge parts matching build_continent.bridge_scene's contract."""
    water_fields=water_fields or L.water_fields
    field=common_surface(world,water_fields=water_fields)
    builder=G.GltfBuilder('Eloria unified continental bridge deck')
    builder.add_material(G.Material('bridge_stone',base_color=(.44,.43,.37,1),roughness=.92))
    builder.add_image('continental_bridge_planks',timber_texture())
    builder.add_material(G.Material('bridge_timber',base_color_texture='continental_bridge_planks',roughness=.93))
    builder.add_material(G.Material('bridge_edge_timber',base_color=(.085,.061,.04,1),roughness=.95,double_sided=True))
    builder.add_material(G.Material('threshold_invisible',base_color=(0,0,0,0),alpha_mode='BLEND'))
    result=[];triangles=[];support_reports=[]
    def add(region,name,mesh):
        builder.add_mesh(name,mesh,with_tangents=False)
        root=builder.add_node(G.Node(name,mesh=name))
        result.append({'region':region,'roots':[root],'bounds':mesh.bounds(),'node':name,'segment':[]})
    # A site whose deck fell into disconnected components names every piece by the site: its floors and fascias are
    # gathered and emitted as one node per territory after the loop, so no two nodes share a name.
    numbers=[component['id'] for component in field['components']]
    shared={number for number in numbers if numbers.count(number)>1};gathered={}
    def floor(region,name,mesh,number):
        if number in shared:gathered.setdefault(name,(region,[]))[1].append(mesh)
        else:add(region,name,mesh)
    for component in field['components']:
        mesh,owners=deck_mesh(world,component)
        faces=mesh.positions[mesh.indices.reshape(-1,3)]
        encoded=faces.astype(np.float32).astype(float)
        normal=np.cross(encoded[:,1]-encoded[:,0],encoded[:,2]-encoded[:,0])
        invalid=(normal[:,1]<=0)|(np.hypot(normal[:,0],normal[:,2])>GRADE*normal[:,1]+1e-10)
        if invalid.any():
            first=np.flatnonzero(invalid)[0];where=encoded[first].mean(axis=0)
            slope=np.hypot(normal[first,0],normal[first,2])/max(normal[first,1],1e-20)
            raise ValueError(f'Quantized bridge floor is not a valid <=.65 slope at {where.tolist()}: grade {slope:.8f}, projected area {normal[first,1]*.5:.9f}m2')
        triangles.append(faces)
        for index,region in enumerate(world.ids):
            selected=np.flatnonzero(owners==index)
            if len(selected):floor(region,f"Walk_ContinentalBridgeUnion_{component['id']:03d}_{region}",subset_mesh(mesh,selected),component['id'])
        fascia,fascia_owners=edge_fascia(mesh,owners,field['outline'])
        if fascia is not None:
            for index,region in enumerate(world.ids):
                selected=np.flatnonzero(fascia_owners==index)
                if len(selected):floor(region,f"BridgeUnionTimberEdge_{component['id']:03d}_{region}",subset_mesh(fascia,selected),component['id'])
        row,col=np.nonzero(component['cells']);sl=component['slice'];planned=[];placed=[];fitted=[]
        for r,c in zip(row,col):
            iz,ix=sl[0].start+int(r),sl[1].start+int(c)
            if ix%8!=4 or iz%8!=4:continue
            x,z=world.x0+(ix+.5)*CELL,world.z0+(iz+.5)*CELL
            if not field['outline'].contains(x,z):continue
            if float(surface_at(world,x,z,field))-.12-float(world.height_at(x,z))<.4:continue
            # Piers stand only under the span, over the water; a landing rests on its bank.
            bed=np.array([float(world.height_at(x,z))])
            if not bool(np.asarray(water_fields(np.array([x]),np.array([z]),height=bed,plan=world.plan)['mask']).reshape(-1)[0]):continue
            planned.append([x,z]);support,fit=fit_pier(world,encoded,x,z);fitted.append(fit)
            if support is None:continue
            placed.append(fit['position']);region=world.ids[int(world.owner_at(*fit['position']))]
            add(region,f"BridgeUnionPier_{component['id']:03d}_{ix}_{iz}",support)
        support_reports.append(dict(component=component['id'],**support_spacing(world,encoded,planned,placed),piers=fitted))
    for name,(region,meshes) in gathered.items():add(region,name,merge_meshes(meshes))
    names=[part['node'] for part in result]
    if len(names)!=len(set(names)):raise ValueError('Bridge parts share a node name: '+', '.join(sorted({n for n in names if names.count(n)>1})))
    world.bridge_triangles=np.concatenate(triangles) if triangles else np.empty((0,3,3))
    world.bridge_field={key:value for key,value in field.items() if key!='components'}
    for connection in world.connections:
        if connection['type']!='walk':continue
        anchor=np.asarray(connection['anchor']);normal=np.asarray(connection['normal'])
        for side,region in enumerate(connection['regions']):
            outward=normal*(1 if side==0 else -1);tangent=np.array([-outward[1],outward[0]])
            corners=np.array([anchor+outward*d+tangent*t for d in (-4,2) for t in (-4,4)])
            lo=corners.min(axis=0);hi=corners.max(axis=0)
            x,z=np.meshgrid(np.arange(lo[0],hi[0]+.5,CELL),np.arange(lo[1],hi[1]+.5,CELL))
            vertices=np.c_[x.ravel(),surface_at(world,x.ravel(),z.ravel(),field),z.ravel()]
            row,col=np.indices((x.shape[0]-1,x.shape[1]-1));a=(row*x.shape[1]+col).ravel();b=a+1;c=a+x.shape[1];d=c+1
            mesh=M.Mesh(positions=vertices,normals=np.tile([0.,1.,0.],(len(vertices),1)),uvs=vertices[:,[0,2]],
                        indices=np.c_[a,c,b,b,c,d].ravel(),material='threshold_invisible')
            mesh.recompute_normals(180)
            add(region,'Walk__StreamThreshold_'+connection['id']+'_'+region,mesh)
    Path(path).parent.mkdir(parents=True,exist_ok=True);builder.write_glb(str(path))
    world.bridge_report={'components':len(field['components']),'visibleCells':int(field['mask'].sum()),
        'visibleTriangles':len(world.bridge_triangles),'wetCells':field['wetCells'],'siteCells':field['siteCells'],'looseWetCells':field['looseWetCells'],
        'riverWaterOutsideSites':field['riverWaterOutsideSites'],'decks':field['decks'],
        'deckLandingMetres':field['deckLandingMetres'],'deckLiftMetres':field['deckLiftMetres'],'trimmedLandingCells':field['trimmedLandingCells'],
        'cutOffLandingCells':field['cutOffLandingCells'],'cutOffLandingBanks':field['cutOffLandingBanks'],
        'maximumBankErrorMetres':field['maximumBankError'],'worstBank':field['worstBank'],'maximumGrade':GRADE,
        'outlineMaximumInsetFraction':1-math.cos(math.pi/(2*CAP_ARC_STEPS)),
        'precisionCleanupAreaSquareMetres':sum(c.get('precisionCleanupArea',0) for c in field['components']),
        'supports':support_reports,
        'policy':'Decks only at claimed crossing sites (span plus landings) and over deep water crossed away from a site; disjoint road capsule union clipped onto one common floor; unchanged terrain; exact ownership by cell; piers only over water; timber fascia below the floor.'}
    return result
