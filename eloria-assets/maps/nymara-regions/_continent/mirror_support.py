"""Local bank clearance beneath Mirrorhold's retained upper walking decks.

Apply after final road/ferry grading, before regrounding/scatter. Geometry and
the city's common translation are immutable. The old source survey includes
a small rise through the City link; lower structural sleepers are deliberately
ignored wherever the actual deck covers them.
"""
from __future__ import annotations
import math
import numpy as np
import landscape as L
import scene_io as S

LINKS=('Landmark_LakeLink_City','Landmark_LakeLink_Sanctuary')
GROUND_CLEARANCE=.06
GRID_APRON=math.sqrt(2)*2.
FEATHER=6.


def walking_triangles(content,obj):
    document,body=content.documents[obj['region']]
    indices=[i for i in S.descendants(document,obj.get('indices',[obj['index']])) if 'mesh' in document['nodes'][i]]
    triangles=S.GR.triangles(document,body,indices)+np.asarray(obj['shift'])
    normal=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
    upward=normal[:,1]>.6*np.maximum(np.linalg.norm(normal,axis=1),1e-10)
    return triangles[upward]


def upper_floor_field(triangles,x,z):
    """Upper exposed floor and nearest footprint distance, including overlaps.

    At a covered point the upper triangle wins. Outside the footprint, project
    onto its actual edges; overlapping sleeper/deck boundaries keep the upper
    deck level instead of creating a false underground walking requirement.
    """
    x,z=np.broadcast_arrays(np.asarray(x,float),np.asarray(z,float))
    distance=np.full(x.shape,np.inf);height=np.full(x.shape,-np.inf)
    for a,b,c in np.asarray(triangles,float):
        ab=b[[0,2]]-a[[0,2]];ac=c[[0,2]]-a[[0,2]]
        det=ab[0]*ac[1]-ab[1]*ac[0]
        if abs(det)<1e-10:continue
        px,pz=x-a[0],z-a[2]
        u=(px*ac[1]-pz*ac[0])/det;v=(ab[0]*pz-ab[1]*px)/det
        inside=(u>=-1e-9)&(v>=-1e-9)&(u+v<=1+1e-9)
        d=np.where(inside,0.,np.inf)
        y=np.where(inside,a[1]+u*(b[1]-a[1])+v*(c[1]-a[1]),-np.inf)
        for start,end in ((a,b),(b,c),(c,a)):
            delta=end-start;length2=delta[0]**2+delta[2]**2
            if length2<1e-12:continue
            t=np.clip(((x-start[0])*delta[0]+(z-start[2])*delta[2])/length2,0,1)
            edge_distance=np.hypot(x-start[0]-t*delta[0],z-start[2]-t*delta[2])
            closer=edge_distance<d-1e-9
            y=np.where(closer,start[1]+t*delta[1],y);d=np.minimum(d,edge_distance)
        closer=d<distance-1e-8;equal=np.abs(d-distance)<=1e-8
        height=np.where(closer,y,np.where(equal,np.maximum(height,y),height))
        distance=np.minimum(distance,d)
    return height,distance


def sample_upper_clearance(world,triangles,step=.25):
    lo=triangles[:,:,[0,2]].min(axis=(0,1));hi=triangles[:,:,[0,2]].max(axis=(0,1))
    x,z=np.meshgrid(np.arange(lo[0],hi[0]+step*.5,step),np.arange(lo[1],hi[1]+step*.5,step))
    # Include actual vertices and centroids so a small shore triangle cannot
    # fall between the independent regular samples.
    extra=np.concatenate((triangles.reshape(-1,3),triangles.mean(axis=1)))
    x=np.r_[x.ravel(),extra[:,0]];z=np.r_[z.ravel(),extra[:,2]]
    floor,distance=upper_floor_field(triangles,x,z);inside=distance<1e-7
    x,z,floor=x[inside],z[inside],floor[inside]
    ground=world.height_at(x,z);burial=ground-floor
    worst=int(np.argmax(burial))
    return {'samples':len(x),'buriedSamples':int(np.count_nonzero(burial>.015)),
            'maximumBurial':float(np.max(burial,initial=0)),
            'minimumClearance':float(np.min(-burial)),
            'worstGlobal':[float(x[worst]),float(z[worst])],
            'worstFloor':float(floor[worst])}


def exposed_triangles(triangles):
    """Discard sleeper/support tops fully covered by the walking deck."""
    weights=np.array([[1/3,1/3,1/3],[.6,.2,.2],[.2,.6,.2],[.2,.2,.6]])
    samples=np.einsum('sj,tjk->tsk',weights,triangles)
    upper,_=upper_floor_field(triangles,samples[:,:,0],samples[:,:,2])
    return triangles[np.any(samples[:,:,1]>=upper-1e-6,axis=1)]


def apply_mirror_support(world,content):
    """Trim only local dry ground that covers a verified exposed link floor."""
    if 'mirrorhold' not in world.ids:return {}
    objects={o['node']:o for o in content.objects if o['region']=='mirrorhold'}
    reports=[]
    for name in LINKS:
        obj=objects.get(name)
        if obj is None or not obj['walk']:raise ValueError(name+': required retained walking link is missing')
        triangles=walking_triangles(content,obj)
        if not len(triangles):raise ValueError(name+': no upward retained walking surface')
        before=sample_upper_clearance(world,triangles)
        entry={'node':name,'before':before,'correctedVertices':0,'maximumCut':0.,'correctedAreaSquareMetres':0.}
        if before['buriedSamples']:
            low=triangles[:,:,[0,2]].min(axis=(0,1))-GRID_APRON-FEATHER
            high=triangles[:,:,[0,2]].max(axis=(0,1))+GRID_APRON+FEATHER
            ix0,iz0=np.maximum(0,np.floor((low-[world.x0,world.z0])/2).astype(int))
            ix1,iz1=np.minimum([len(world.x),len(world.z)],np.ceil((high-[world.x0,world.z0])/2).astype(int)+1)
            sl=np.s_[iz0:iz1,ix0:ix1]
            dry=~world.water['mask'][sl]
            old=world.height[sl].copy()
            updated=old.copy()
            visible=exposed_triangles(triangles)
            for face in visible:
                floor,distance=upper_floor_field(face[None,:,:],world.gx[sl],world.gz[sl])
                weight=(1-L.smoothstep(GRID_APRON,GRID_APRON+FEATHER,distance))*dry
                cap=floor-GROUND_CLEARANCE
                # Every terrain triangle touching a deck edge must stay below
                # that floor. A nearby higher rail cannot override this cap.
                updated=np.minimum(updated,old-weight*np.maximum(0,old-cap))
            cut=old-updated
            if float(cut.max(initial=0))>2.0:
                raise ValueError(name+': bank correction exceeds its bounded 2 m local repair; redesign the approach')
            changed=cut>1e-8
            world.height[sl]=updated
            world.assembly_target[sl]=np.where(changed,np.minimum(world.assembly_target[sl],updated),world.assembly_target[sl])
            entry.update(correctedVertices=int(changed.sum()),maximumCut=float(cut.max(initial=0)),
                         correctedAreaSquareMetres=float(changed.sum()*4),
                         exposedFloorTriangles=len(visible),
                         correctedBounds=[[float(world.gx[sl][changed].min()),float(world.gz[sl][changed].min())],
                                          [float(world.gx[sl][changed].max()),float(world.gz[sl][changed].max())]])
        entry['after']=sample_upper_clearance(world,triangles)
        if entry['after']['maximumBurial']>.015:
            raise ValueError(name+': actual upper walking floor remains buried after local bank repair')
        reports.append(entry)
    report={'policy':'Actual exposed upper link floors; bounded local dry bank cuts, unchanged city geometry and lake',
            'groundClearanceMetres':GROUND_CLEARANCE,'fullGridApronMetres':GRID_APRON,'featherMetres':FEATHER,
            'links':reports}
    world.mirror_support=report
    return report
