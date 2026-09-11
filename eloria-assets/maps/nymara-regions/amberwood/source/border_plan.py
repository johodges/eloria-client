"""Three land marches with a visible continuation into the next landscape."""
from pathlib import Path
import numpy as np
from border_vistas import add_vista
import compact_plan as C

def finish(build):
    # Keep ordinary directional signs and sheltered road stations. The country
    # beyond, rather than a dedicated marker, announces the handoff.
    removed={p.node for p in build.placements if p.node.startswith('March_') and
             (p.node.endswith('_Stone') or '_Furniture_' in p.node) and 'harbour' not in p.node}
    build.placements[:]=[p for p in build.placements if p.node not in removed]
    for l in build.landmarks:
        if l.get('node') in removed:
            l['node']=l['node'].replace('_Stone','_Signpost')
            l['note']='A changing landscape and an ordinary direction sign mark this border road.'
    root=Path(__file__).resolve().parents[2]
    corridors=[(np.array([float(C.PLAN.x(x)),float(C.PLAN.z(z))]),np.array(d))
               for x,z,d in [(72,-384,(0,-1)),(393,-66,(1,0)),(156,162,(0,1))]]
    def keep(p):
        if p.kind not in ('tree','foliage','undergrowth','rock','fallenlog'):return True
        point=np.array(p.position)[[0,2]]
        for origin,forward in corridors:
            delta=point-origin;side=np.array([-forward[1],forward[0]])
            if -30<float(delta@forward)<40 and abs(float(delta@side))<17:return False
        return True
    build.placements[:]=[p for p in build.placements if keep(p)]
    build.border_vistas=[]
    for region,portal,edge,outward,inward,material in [
        ('mirrorhold','west-gorge',(269,float(C.PLAN.z(-66))),(1,0),(1,0),'alpine_turf'),
        ('grey_moors','north-gate',(float(C.PLAN.x(156)),118),(0,1),(0,1),'grey_heather_moor')]:
        build.border_vistas.append(add_vista(build,root/region,portal,edge,outward,inward,material,region))
    from streaming_borders import apply as stitch_border
    stitch_border(build, 'amberwood')
    # Grove markers name a place, not one indispensable scatter instance.
    # Keep their logical centres but attach them to a surviving constituent.
    nodes={p.node for p in build.placements}
    for landmark in build.landmarks:
        node=landmark.get('node','')
        family=next((p for p in ('Grove_','Orchard_') if node.startswith(p)),None)
        if node in nodes or family is None:continue
        choices=[p for p in build.placements if p.node.startswith(family) and p.node.endswith('_Wood')]
        if choices:
            centre=np.array(landmark['position'])[[0,2]]
            landmark['node']=min(choices,key=lambda p:np.linalg.norm(np.array(p.position)[[0,2]]-centre)).node
