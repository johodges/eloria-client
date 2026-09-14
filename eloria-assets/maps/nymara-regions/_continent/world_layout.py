"""One sampled continent, followed by named ownership and travel planning."""
from __future__ import annotations
import heapq
import math
import numpy as np
from scipy.ndimage import gaussian_filter, distance_transform_edt, binary_dilation
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import cg
import landscape as L

CELL=2.0
CHUNK=96.0


def graded_profile(target, distances, floor=None, maximum_grade=.35):
    """A bounded-grade cut/fill profile, constrained above any water crossing."""
    target=np.asarray(target,float);distance=np.asarray(distances,float)
    if len(target)<2:return target.copy()
    step=np.diff(distance)*maximum_grade
    def envelope(values,upper):
        result=values.copy();operation=max if upper else min
        sign=-1 if upper else 1
        for i in range(1,len(result)):result[i]=operation(result[i],result[i-1]+sign*step[i-1])
        for i in range(len(result)-2,-1,-1):result[i]=operation(result[i],result[i+1]+sign*step[i])
        return result
    floor=np.full_like(target,-np.inf) if floor is None else np.asarray(floor,float)
    floor=envelope(floor,True)
    left=max(target[0],floor[0]);right=max(target[-1],floor[-1])
    # Endpoint cuts are shared with the dry roadbed; this protects a pass from
    # an impossible abrupt step while preserving all water clearance.
    if left>right+maximum_grade*distance[-1]:right=left-maximum_grade*distance[-1]
    if right>left+maximum_grade*distance[-1]:left=right-maximum_grade*distance[-1]
    lower=np.maximum(floor,np.maximum(left-maximum_grade*distance,right-maximum_grade*(distance[-1]-distance)))
    upper=np.minimum(left+maximum_grade*distance,right+maximum_grade*(distance[-1]-distance))
    if np.any(lower>upper+1e-6):raise ValueError('Water clearance exceeds the available bridge approach length')
    smooth=gaussian_filter(target,sigma=2,mode='nearest')
    result=(envelope(smooth,False)+envelope(smooth,True))*.5
    return np.maximum(lower,np.minimum(upper,result))


def corridor_grade(target, active, maximum_grade=.45):
    """Reconcile intersecting roads as one surface, including each junction.

    Axis-constrained lower and upper envelopes bound the actual triangle
    gradient, rather than only a road's longitudinal centreline slope.
    """
    lower=np.where(active,target,-np.inf).copy()
    upper=np.where(active,target,np.inf).copy()
    step=CELL*maximum_grade/math.sqrt(2)
    for _ in range(sum(active.shape)):
        lo=lower.copy();hi=upper.copy()
        for dst,src in ((np.s_[1:,:],np.s_[:-1,:]),(np.s_[:-1,:],np.s_[1:,:]),
                        (np.s_[:,1:],np.s_[:,:-1]),(np.s_[:,:-1],np.s_[:,1:])):
            lo[dst]=np.maximum(lo[dst],lower[src]-step)
            hi[dst]=np.minimum(hi[dst],upper[src]+step)
        lo[~active]=-np.inf;hi[~active]=np.inf
        difference=max(np.max(lo[active]-lower[active],initial=0),np.max(upper[active]-hi[active],initial=0))
        lower,upper=lo,hi
        if difference<1e-7:
            result=target.copy();result[active]=(lo[active]+hi[active])*.5
            return result
    raise ValueError('Shared road junction grading did not converge')


def fit_road_to_footings(target,active,fixed_height,fixed,maximum_grade=.60):
    """Fit approaches to immutable courtyard floors through the road graph."""
    if not np.any(fixed):return target,0
    lower=np.where(fixed,fixed_height,-np.inf);upper=np.where(fixed,fixed_height,np.inf)
    step=CELL*maximum_grade/math.sqrt(2)
    for _ in range(sum(active.shape)):
        lo=lower.copy();hi=upper.copy()
        for dst,src in ((np.s_[1:,:],np.s_[:-1,:]),(np.s_[:-1,:],np.s_[1:,:]),
                        (np.s_[:,1:],np.s_[:,:-1]),(np.s_[:,:-1],np.s_[:,1:])):
            lo[dst]=np.maximum(lo[dst],lower[src]-step)
            hi[dst]=np.minimum(hi[dst],upper[src]+step)
        lo[~active]=-np.inf;hi[~active]=np.inf
        if np.array_equal(lo,lower) and np.array_equal(hi,upper):break
        lower,upper=lo,hi
    feasible=active&(lower<=upper+1e-6)
    # Contradictory architectural pins still require a continuous roadbed.
    # Leaving the unrelated original target in just the infeasible cells cuts
    # a cliff along their boundary with fitted cells. Both propagated envelopes
    # have the same graph grade bound; ordering and clipping between them keeps
    # that bound across the entire road. Actual footings are restored separately
    # by settle_roads, and the conflict count/strict collision retain any real
    # architectural impossibility for redesign instead of hiding it here.
    low=np.minimum(lower,upper);high=np.maximum(lower,upper)
    result=target.copy();result[active]=np.clip(result[active],low[active],high[active])
    return result,int(np.count_nonzero(active&~feasible))


def road_shoulder_field(target,active,base,distance,fixed=None):
    """Blend adjacent road banks without nearest-road Voronoi walls.

    Every solved road vertex remains a Dirichlet boundary. Actual structure
    cores and ground beyond the 24 m shoulder are also fixed. Only the empty
    exterior bank interpolates between those geographic constraints.
    """
    fixed=np.zeros_like(active) if fixed is None else np.asarray(fixed,bool)
    free=(distance<24.)&~active&~fixed
    free[[0,-1],:]=False;free[:,[0,-1]]=False
    result=np.asarray(base,float).copy();result[active]=target[active]
    if not free.any():return result
    count=int(free.sum());index=np.full(active.shape,-1,np.int32);index[free]=np.arange(count)
    rows=[np.arange(count)];cols=[rows[0]];values=[np.full(count,4.)]
    rhs=np.zeros(count)
    for axis,offset in ((0,-1),(0,1),(1,-1),(1,1)):
        adjacent=np.roll(index,offset,axis=axis)[free];interior=adjacent>=0
        rows.append(np.flatnonzero(interior));cols.append(adjacent[interior]);values.append(np.full(int(interior.sum()),-1.))
        boundary=np.roll(result,offset,axis=axis)[free]
        rhs+=np.where(interior,0.,boundary)
    matrix=coo_matrix((np.concatenate(values),(np.concatenate(rows),np.concatenate(cols))),shape=(count,count)).tocsr()
    solution,status=cg(matrix,rhs,x0=result[free],rtol=1e-8,atol=1e-6,maxiter=400)
    if status or not np.isfinite(solution).all():raise ValueError('Road exterior shoulder solve did not converge')
    result[free]=solution
    return result


def outline(mask, x0, z0, cell=CELL):
    """Trace the exact outer boundary of a connected pixel ownership mask."""
    mask=np.asarray(mask,bool)
    padded=np.pad(mask,1)
    edges={}
    for dz,dx,a,b in ((-1,0,(0,0),(1,0)),(0,1,(1,0),(1,1)),(1,0,(1,1),(0,1)),(0,-1,(0,1),(0,0))):
        exposed=mask & ~padded[1+dz:1+dz+mask.shape[0],1+dx:1+dx+mask.shape[1]]
        zs,xs=np.nonzero(exposed)
        for z,x in zip(zs.tolist(),xs.tolist()): edges[(x+a[0],z+a[1])]=(x+b[0],z+b[1])
    if not edges: return []
    start=min(edges,key=lambda p:(p[1],p[0]));points=[start];current=edges[start]
    while current!=start:
        points.append(current)
        if current not in edges: raise ValueError('Ownership contour is open')
        current=edges[current]
        if len(points)>len(edges): raise ValueError('Ownership contour did not close')
    result=[]
    for i,p in enumerate(points):
        a=np.subtract(p,points[i-1]);b=np.subtract(points[(i+1)%len(points)],p)
        if a[0]*b[1]!=a[1]*b[0]: result.append([x0+p[0]*cell,z0+p[1]*cell])
    return result


def triangle_sample(grid,x,z,x0=0,z0=0,cell=CELL):
    x,z=np.broadcast_arrays(np.asarray(x,float),np.asarray(z,float))
    fx=np.clip((x-x0)/cell,0,grid.shape[1]-1.0000001)
    fz=np.clip((z-z0)/cell,0,grid.shape[0]-1.0000001)
    ix,iz=fx.astype(int),fz.astype(int);u,v=fx-ix,fz-iz
    a,b,c,d=grid[iz,ix],grid[iz,ix+1],grid[iz+1,ix],grid[iz+1,ix+1]
    return np.where(u+v<=1,a+(b-a)*u+(c-a)*v,d+(c-d)*(1-u)+(b-d)*(1-v))


class World:
    def hub(self,region):
        """Inhabited arrival is independent of the territory's geographic seed."""
        return np.asarray(self.plan.get('inhabited_hubs',{}).get(region,self.regions[region]['center']),float)

    def __init__(self, plan=None):
        self.plan=L.load_plan() if plan is None else plan
        self.regions={r['id']:r for r in self.plan['regions']}
        self.ids=list(self.regions)
        self.centers=np.array([r['center'] for r in self.regions.values()],float)
        self.x0,self.z0,self.x1,self.z1=self.plan['bounds']
        self.x=np.arange(self.x0,self.x1+CELL*.5,CELL)
        self.z=np.arange(self.z0,self.z1+CELL*.5,CELL)
        self.gx,self.gz=np.meshgrid(self.x,self.z)
        self.height=L.height_at(self.gx,self.gz,self.plan)
        self.water=L.water_fields(self.gx,self.gz,height=self.height,plan=self.plan)
        self.original_height=self.height.copy()
        centers=np.c_[self.gx[:-1,:-1].ravel()+CELL*.5,self.gz[:-1,:-1].ravel()+CELL*.5]
        scores=np.full(len(centers),np.inf);owners=np.zeros(len(centers),int)
        for index,(region,center) in enumerate(zip(self.ids,self.centers)):
            score=np.sum((centers-center)**2,axis=1)-self.plan.get('ownership_bias',{}).get(region,0)
            selected=score<scores;owners[selected]=index;scores[selected]=score[selected]
        self.owner=owners.reshape(self.height.shape[0]-1,self.height.shape[1]-1)
        self.polygons={r:outline(self.owner==i,self.x0,self.z0) for i,r in enumerate(self.ids)}
        self.obstacles=np.zeros_like(self.height,dtype=bool)
        self.roads=[]
        self.road_distance=np.full_like(self.height,np.inf)
        self.road_nearest=np.full_like(self.height,np.inf)
        self.road_target=self.height.copy()
        self.foundation_weight=np.zeros_like(self.height)
        self.foundation_target=np.zeros_like(self.height)
        self.assembly_weight=np.zeros_like(self.height)
        self.assembly_target=self.height.copy()
        self.connections=[]
        self.quay_contacts=[]

    def height_at(self,x,z): return triangle_sample(self.height,x,z,self.x0,self.z0)

    def bounds(self,region):
        p=np.array(self.polygons[region]);return p.min(axis=0),p.max(axis=0)

    def address(self,region):
        lo,hi=self.bounds(region);center=self.centers[self.ids.index(region)]
        local_lo=np.floor(lo-center)-4;local_hi=np.ceil(hi-center)+4
        cells=int(math.ceil(max(local_hi-local_lo)/6)*6)
        origin=[int(-local_lo[0]),int(local_hi[1])]
        return origin,[cells,cells]

    def owner_at(self,x,z):
        ix=np.clip(((np.asarray(x)-self.x0)/CELL).astype(int),0,self.owner.shape[1]-1)
        iz=np.clip(((np.asarray(z)-self.z0)/CELL).astype(int),0,self.owner.shape[0]-1)
        outside=(np.asarray(x)<self.x0)|(np.asarray(x)>self.x1)|(np.asarray(z)<self.z0)|(np.asarray(z)>self.z1)
        return np.where(outside,-1,self.owner[iz,ix])

    def foundation(self,center,radius,height,feather=16,obstacle=False):
        """Accumulate compatible footing constraints; settle all sites together."""
        x,z=center
        ix0=max(0,int((x-radius-feather-self.x0)/CELL));ix1=min(len(self.x),int((x+radius+feather-self.x0)/CELL)+2)
        iz0=max(0,int((z-radius-feather-self.z0)/CELL));iz1=min(len(self.z),int((z+radius+feather-self.z0)/CELL)+2)
        sl=np.s_[iz0:iz1,ix0:ix1]
        d=np.hypot(self.gx[sl]-x,self.gz[sl]-z)
        weight=1-L.smoothstep(radius,radius+feather,d)
        self.foundation_weight[sl]+=weight
        self.foundation_target[sl]+=weight*height
        if obstacle: self.obstacles[sl]|=d<max(1,radius-1)

    def settle_foundations(self):
        weight=np.clip(self.foundation_weight,0,1)
        target=self.foundation_target/np.maximum(self.foundation_weight,1e-12)
        self.height=self.original_height*(1-weight)+target*weight
        self.height=self.height*(1-self.assembly_weight)+self.assembly_target*self.assembly_weight
        # Drainage remains the global authority beneath any settlement. A
        # structure spanning a channel needs a real floor and supports.
        river=self.water['river_mask']&(self.water['depth']>.35)
        self.height[river]=self.original_height[river]
        self.restore_drainage_corridor('foundations')
        self.water=L.water_fields(self.gx,self.gz,height=self.height,plan=self.plan)

    def restore_drainage_corridor(self,stage):
        """Keep the natural bank apron through later cut/fill operations.

        Real footing cores stay fixed. A 32 m transition around them preserves
        settlement support without cutting a hard rectangular hole in the bank
        protection. Raised road profiles are retained for the bridge exporter.
        """
        natural=L.water_fields(self.gx,self.gz,height=self.original_height,plan=self.plan)
        channel=natural['river_mask']
        if not np.any(channel):return
        distance=distance_transform_edt(~channel)*CELL
        apron=1-L.smoothstep(10,42,distance)
        hard=self.assembly_weight>=.999
        for quay in getattr(self,'quay_contacts',[]):
            hard|=np.hypot(self.gx-quay['center'][0],self.gz-quay['center'][1])<=4
        # Channel beds were already made authoritative by the calling stage.
        # Buildings alongside them are retained, but cannot fill flowing water.
        hard&=~channel
        clearance=distance_transform_edt(~hard)*CELL if np.any(hard) else np.full_like(apron,np.inf)
        weight=apron*L.smoothstep(0,32,clearance)
        conflict=hard&(apron>.05)&(np.abs(self.height-self.original_height)>.5)
        delta=self.height-self.original_height
        before=self.height.copy()
        self.height=self.height*(1-weight)+self.original_height*weight
        self.height[channel]=self.original_height[channel]
        report={'apronMetres':10,'outerMetres':42,'footingFeatherMetres':32,
            'restoredVertices':int(np.count_nonzero(weight>0)),
            'conflictingHardVertices':int(conflict.sum()),
            'maximumRetainedFill':float(np.max(delta[conflict],initial=0)),
            'maximumRetainedCut':float(np.max(-delta[conflict],initial=0)),
            'maximumCorrection':float(np.max(np.abs(self.height-before),initial=0))}
        if not hasattr(self,'drainage_restoration'):self.drainage_restoration={}
        self.drainage_restoration[stage]=report
        self.water=L.water_fields(self.gx,self.gz,height=self.height,plan=self.plan)
        return report

    def assembly_foundation(self,sl,target,weight):
        replace=weight>self.assembly_weight[sl]
        self.assembly_target[sl]=np.where(replace,target,self.assembly_target[sl])
        self.assembly_weight[sl]=np.maximum(self.assembly_weight[sl],weight)

    def structure_obstacle(self,low,high,clearance=6):
        """Keep road and grove placement outside actual structure bounds."""
        lo=np.asarray(low)[[0,2]]-clearance;hi=np.asarray(high)[[0,2]]+clearance
        ix0=max(0,int((lo[0]-self.x0)/CELL));ix1=min(len(self.x),int((hi[0]-self.x0)/CELL)+2)
        iz0=max(0,int((lo[1]-self.z0)/CELL));iz1=min(len(self.z),int((hi[1]-self.z0)/CELL)+2)
        self.obstacles[iz0:iz1,ix0:ix1]=True

    def prepare_quay_court(self,center):
        d=np.hypot(self.gx-center[0],self.gz-center[1])
        elevation=max(1.8,float(self.height_at(*center)))
        dry=~self.water['mask']
        weight=(1-L.smoothstep(4,12,d))*dry
        self.height=self.height*(1-weight)+elevation*weight
        self.quay_contacts.append({'center':list(center),'elevation':elevation})

    def settle_roads(self):
        if not self.roads:return
        # All full-width roads agree before any shoulders are blended. This
        # prevents the last outgoing road from cutting a cliff through another.
        # Include a full triangle ring outside the walking corridor. Otherwise
        # a half-metre server sample at a bend can share an ungraded shoulder
        # vertex even though the centreline itself has an acceptable grade.
        active=binary_dilation(self.road_distance<=1.65,iterations=1)
        target=corridor_grade(self.road_target,active)
        dz,dx=np.gradient(self.assembly_target,CELL)
        footing_weight=getattr(self,'road_footing_weight',self.assembly_weight)
        fixed=active&(footing_weight>=.999)&(np.hypot(dx,dz)<.5)&~self.water['mask']
        fixed_height=self.assembly_target.copy();quay_fixed=np.zeros_like(active)
        for quay in self.quay_contacts:
            d=np.hypot(self.gx-quay['center'][0],self.gz-quay['center'][1])
            mask=active&(d<=4)&~self.water['mask']
            fixed_height[mask]=quay['elevation'];fixed|=mask;quay_fixed|=mask
        from ferry_support import road_shore_constraints,restore_graded_shores
        ferry_fixed,ferry_height=road_shore_constraints(self,active)
        fixed_height[ferry_fixed]=ferry_height[ferry_fixed];fixed|=ferry_fixed
        target,conflicts=fit_road_to_footings(target,active,fixed_height,fixed)
        distance=distance_transform_edt(~active)*CELL
        footing_weight=getattr(self,'road_footing_weight',self.assembly_weight)
        target=road_shoulder_field(target,active,self.height,distance,footing_weight>=.999)
        weight=1-L.smoothstep(0,24,distance)
        wet=self.water['mask']&(self.water['depth']>.35)
        weight[wet]=0
        self.height=self.height*(1-weight)+target*weight
        # Built courtyards and thresholds retain their surveyed support plane.
        # Roads approach these constraints; they cannot excavate beneath them.
        support=np.where(active,(footing_weight>=.999).astype(float),footing_weight)
        protected=self.height*(1-support)+self.assembly_target*support
        self.height=np.where(wet,self.height,protected)
        self.height[quay_fixed]=fixed_height[quay_fixed]
        self.restore_drainage_corridor('roads')
        restore_graded_shores(self,active)
        target[ferry_fixed]=self.height[ferry_fixed]
        for road in self.roads:
            points=np.asarray(road['points'],float)
            points[:,1]=triangle_sample(target,points[:,0],points[:,2],self.x0,self.z0)
            road['points']=points.tolist()
        self.road_grading={'corridorVertices':int(active.sum()),'targetMaximumTriangleGrade':.45,
            'fixedFootingVertices':int(fixed.sum()),'conflictingFootingCorridorVertices':conflicts,
            'exceptions':'Original drainage beds and surveyed assembly support remain authoritative; exported collision and bridge tests verify actual traversability.'}

    def adjacent_edges(self):
        pairs={}
        # Every edge is an actual common terrain grid edge, so reciprocal
        # samples and server addresses share exact metre coordinates.
        for axis in (0,1):
            a=self.owner[:-1,:] if axis==0 else self.owner[:,:-1]
            b=self.owner[1:,:] if axis==0 else self.owner[:,1:]
            zs,xs=np.nonzero(a!=b)
            for z,x in zip(zs.tolist(),xs.tolist()):
                ia,ib=int(a[z,x]),int(b[z,x]);pair=tuple(sorted((ia,ib)))
                if axis==0:
                    start=[self.x0+x*CELL,self.z0+(z+1)*CELL];end=[start[0]+CELL,start[1]]
                else:
                    start=[self.x0+(x+1)*CELL,self.z0+z*CELL];end=[start[0],start[1]+CELL]
                pairs.setdefault(pair,[]).append([start,end])
        return pairs

    def plan_connections(self):
        desired=[('whitehorn_range','grey_moors'),('whitehorn_range','amberwood'),('whitehorn_range','amethyst_barrens'),
            ('grey_moors','amberwood'),('grey_moors','westhaven'),('amberwood','mirrorhold'),('amberwood','four_gates'),
            ('mirrorhold','amethyst_barrens'),('mirrorhold','sunmane_steppe'),('mirrorhold','four_gates'),
            ('mirrorhold','verdant_stair'),('amethyst_barrens','sunmane_steppe'),('sunmane_steppe','verdant_stair'),
            ('four_gates','westhaven'),('four_gates','manymouth_delta'),('westhaven','manymouth_delta'),
            ('manymouth_delta','verdant_stair'),('verdant_stair','ssarathi_ruins')]
        edges=self.adjacent_edges()
        for ra,rb in desired:
            ia,ib=self.ids.index(ra),self.ids.index(rb);pair=tuple(sorted((ia,ib)))
            if pair not in edges: continue
            segments=np.array(edges[pair]);mid=segments.mean(axis=1)
            heights=self.height_at(mid[:,0],mid[:,1])
            water=L.water_fields(mid[:,0],mid[:,1],height=heights,plan=self.plan)
            ca,cb=self.centers[ia],self.centers[ib]
            score=np.linalg.norm(mid-ca,axis=1)+np.linalg.norm(mid-cb,axis=1)+heights*.9+water['depth'].clip(0)*45
            # Pick a straight 14m run where possible for seven crossing lanes.
            straight=[]
            by_axis={}
            for i,s in enumerate(segments):
                vertical=abs(s[0,0]-s[1,0])<1e-8
                constant=s[0,0] if vertical else s[0,1]
                variable=mid[i,1] if vertical else mid[i,0]
                by_axis.setdefault((vertical,constant),set()).add(variable)
            for i,s in enumerate(segments):
                vertical=abs(s[0,0]-s[1,0])<1e-8;constant=s[0,0] if vertical else s[0,1];variable=mid[i,1] if vertical else mid[i,0]
                available=by_axis[(vertical,constant)]
                if all(variable+k*CELL in available for k in range(-3,4)): straight.append(i)
            candidates=np.array(straight if straight else range(len(mid)))
            # The full receiving footprint must belong to the two actual
            # neighbours. A triple junction cannot supply seven safe lanes.
            safe=[]
            for candidate in candidates:
                x,z=mid[candidate]
                xx,zz=np.meshgrid(x+np.arange(-5,6),z+np.arange(-5,6))
                if np.isin(self.owner_at(xx,zz),(ia,ib)).all():safe.append(candidate)
            if not safe:raise ValueError(f'{ra}/{rb}: no crossing clear of the third territory or world edge')
            candidates=np.asarray(safe)
            identity='--'.join(sorted((ra,rb)))
            authored=self.plan.get('connection_sites',{}).get(identity)
            if authored is None:
                index=int(candidates[np.argmin(score[candidates])])
            else:
                delta=np.linalg.norm(mid[candidates]-np.asarray(authored,float),axis=1)
                if delta.min()>1e-6:
                    raise ValueError(identity+': authored crossing is not a safe shared boundary station')
                index=int(candidates[np.argmin(delta)])
            anchor=mid[index]
            vertical=abs(segments[index,0,0]-segments[index,1,0])<1e-8
            normal=np.array([1.,0.]) if vertical else np.array([0.,1.])
            if np.dot(normal,cb-ca)<0: normal=-normal
            self.connections.append({'id':identity,'type':'walk','regions':[ra,rb],
                                     'anchor':anchor.tolist(),'normal':normal.tolist(),'edgeSegments':segments.tolist()})
        for ra,rb in (('westhaven','crownwater'),('manymouth_delta','crownwater'),('ssarathi_ruins','crownwater')):
            self.connections.append({'id':'--'.join(sorted((ra,rb))),'type':'ferry','regions':[ra,rb]})

    def route(self,start,goal,region=None,step=6):
        """A* road alignment that favours manageable grades and narrow crossings."""
        stride=max(1,int(step/CELL));h=self.height[::stride,::stride];spacing=stride*CELL
        def node(point): return (int(np.clip(round((point[1]-self.z0)/spacing),0,h.shape[0]-1)),int(np.clip(round((point[0]-self.x0)/spacing),0,h.shape[1]-1)))
        origin,target=node(start),node(goal)
        if origin==target:return np.vstack([np.asarray(start,float),np.asarray(goal,float)])
        region_id=self.ids.index(region) if region else None
        civic=(self.mirror_street_distance[::stride,::stride]<=1.25
               if region=='mirrorhold' and hasattr(self,'mirror_street_distance') else None)
        costs={origin:0.};parents={};queue=[(0.,origin)];done=set()
        while queue:
            _,current=heapq.heappop(queue)
            if current in done:continue
            if current==target:break
            done.add(current);z,x=current
            for dz,dx in ((-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)):
                nz,nx=z+dz,x+dx
                if not(0<=nz<h.shape[0] and 0<=nx<h.shape[1]):continue
                neighbor=(nz,nx)
                if neighbor in done:continue
                gx,gz=self.x0+nx*spacing,self.z0+nz*spacing
                if region_id is not None and int(self.owner_at(gx,gz))!=region_id:continue
                length=math.hypot(dx,dz)*spacing;grade=abs(h[nz,nx]-h[z,x])/length
                blocked=self.obstacles[min(nz*stride,self.height.shape[0]-1),min(nx*stride,self.height.shape[1]-1)]
                penalty=1+grade*grade*32+max(0,grade-.4)*70+(65 if h[nz,nx]<.3 else 0)+(150 if blocked and neighbor not in (origin,target) else 0)
                # In the steep city, the surveyed civic network provides the
                # real switchbacks between terraces. Prefer its circulation
                # over cutting a competing shortcut through the city slope.
                if civic is not None and civic[nz,nx] and not blocked:penalty*=.05
                cost=costs[current]+length*penalty
                if cost<costs.get(neighbor,np.inf):
                    costs[neighbor]=cost;parents[neighbor]=current
                    heuristic=math.hypot(nx-target[1],nz-target[0])*spacing
                    if civic is not None:heuristic*=.05
                    heapq.heappush(queue,(cost+heuristic,neighbor))
        if target not in costs: raise ValueError(f'No road alignment from {start} to {goal} in {region}')
        path=[target]
        while path[-1]!=origin:path.append(parents[path[-1]])
        points=np.array([[self.x0+x*spacing,self.z0+z*spacing] for z,x in reversed(path)])
        points[0]=start;points[-1]=goal
        # A broad low-pass bend removes eight-direction grid kinks; endpoints
        # remain the exact surveyed road mouths.
        if len(points)>5:
            smoothed=gaussian_filter(points,sigma=(1.2,0),mode='nearest')
            smoothed[:2]=points[:2];smoothed[-2:]=points[-2:]
            # A curve must not cut the inside of a bend through a building.
            iz=np.clip(((smoothed[:,1]-self.z0)/CELL).astype(int),0,len(self.z)-1)
            ix=np.clip(((smoothed[:,0]-self.x0)/CELL).astype(int),0,len(self.x)-1)
            valid=~self.obstacles[iz,ix];points[valid]=smoothed[valid]
        if civic is not None:
            from mirror_streets import trim_civic_approach
            points=trim_civic_approach(self,points)
        return points

    def add_road(self,points,width=3.5,name='road'):
        points=np.asarray(points,float)
        dense=[]
        for a,b in zip(points,points[1:]):
            count=max(1,int(np.ceil(np.linalg.norm(b-a)/2)))
            dense.extend(a+(b-a)*t for t in np.arange(count)/count)
        points=np.vstack([dense,points[-1]])
        heights=self.height_at(points[:,0],points[:,1])
        water=L.water_fields(points[:,0],points[:,1],height=heights,plan=self.plan)
        floor=np.where(water['mask']&(water['depth']>.35),water['surface']+.85,-np.inf)
        distances=np.r_[0,np.cumsum(np.linalg.norm(np.diff(points,axis=0),axis=1))]
        profile=graded_profile(heights,distances,floor)
        self.roads.append({'id':name,'points':np.c_[points[:,0],profile,points[:,1]].tolist(),'width':width})
        for i,(a,b) in enumerate(zip(points,points[1:])):
            shoulder=max(16,width*4)
            low=np.minimum(a,b)-width-shoulder;high=np.maximum(a,b)+width+shoulder
            ix0=max(0,int((low[0]-self.x0)/CELL));ix1=min(len(self.x),int((high[0]-self.x0)/CELL)+2)
            iz0=max(0,int((low[1]-self.z0)/CELL));iz1=min(len(self.z),int((high[1]-self.z0)/CELL)+2)
            sl=np.s_[iz0:iz1,ix0:ix1];dx,dz=b-a
            t=np.clip(((self.gx[sl]-a[0])*dx+(self.gz[sl]-a[1])*dz)/max(dx*dx+dz*dz,1e-9),0,1)
            d=np.hypot(self.gx[sl]-a[0]-t*dx,self.gz[sl]-a[1]-t*dz)
            self.road_distance[sl]=np.minimum(self.road_distance[sl],d/width)
            target=profile[i]*(1-t)+profile[i+1]*t
            closer=d<self.road_nearest[sl]
            self.road_target[sl]=np.where(closer,target,self.road_target[sl])
            self.road_nearest[sl]=np.minimum(self.road_nearest[sl],d)
