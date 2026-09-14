from pathlib import Path
from types import SimpleNamespace
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import mirror_access_geometry as A
import scene_io as S
import collision_export as C


def test_encoded_stone_ramp_meets_real_contacts_and_walking_grade():
    world=SimpleNamespace(height_at=lambda x,z: .1*np.asarray(x)+3*np.exp(-(np.asarray(x)/4)**2))
    content=SimpleNamespace(documents={'mirrorhold':({},b'')},objects=[])
    mesh,report=A.ramp_mesh(world,content,[-20.,0.],[20.,0.],'stone')
    assert report['maximumGrade']<=.65
    assert max(report['contactLift'])<.026
    assert min(mesh.positions[:,1]-world.height_at(mesh.positions[:,0],mesh.positions[:,2]))>=.0249
    assert report['maximumSupportHeight']>.5


def test_foundation_faces_reach_actual_ground_below_the_walking_surface():
    mesh=A.M.box((8.,.1,4.),center=(0,5,0),material='stone')
    # A real ramp surface has an open edge, unlike a closed box.
    mesh.indices=np.array([0,1,2])
    world=SimpleNamespace(height_at=lambda x,z: np.zeros_like(x))
    foundation=A.foundation_faces(world,mesh,'stone')
    assert foundation.positions[:,1].min()==-.12
    assert foundation.positions[:,1].max()<mesh.positions[:,1].max()


def test_sanctuary_opening_changes_only_a_local_parapet_and_preserves_floor(tmp_path):
    builder=A.G.GltfBuilder('test')
    builder.add_material(A.G.Material('stone'))
    root=builder.add_node(A.G.Node('Landmark_LakeLink_Sanctuary'))
    for name,size,center in [('Walk_Deck',(22.,.2,5.),(866.5,85.3,874.5)),
                              ('Parapet',(20.,1.2,.6),(866.5,85.8,874.5))]:
        builder.add_mesh(name,A.M.box(size,center=center,material='stone'))
        builder.add_node(A.G.Node(name,mesh=name),parent=root)
    path=tmp_path/'source.glb';builder.write_glb(str(path));doc,body=S.GR.load(path)
    floor_index=next(i for i,n in enumerate(doc['nodes']) if n.get('name')=='Walk_Deck')
    rail_index=next(i for i,n in enumerate(doc['nodes']) if n.get('name')=='Parapet')
    before_floor=S.GR.triangles(doc,body,[floor_index]);before_rail=S.GR.triangles(doc,body,[rail_index])
    obj={'index':root,'node':'Landmark_LakeLink_Sanctuary','shift':np.zeros(3)}
    content=SimpleNamespace(documents={'mirrorhold':(doc,body)},placement_by_name={('mirrorhold',obj['node']):obj})
    report=A.open_sanctuary_landing(content);after_doc,after_body=content.documents['mirrorhold']
    np.testing.assert_array_equal(S.GR.triangles(after_doc,after_body,[floor_index]),before_floor)
    assert after_body[:len(body)]==body
    assert doc['nodes'][rail_index]['mesh']!=after_doc['nodes'][rail_index]['mesh']
    after_rail=S.GR.triangles(after_doc,after_body,[rail_index])
    surface=np.full((20,50),85.4)
    before=C.structural_mask([(before_rail,False)],surface,854.,880.)
    after=C.structural_mask([(after_rail,False)],surface,854.,880.)
    assert before[11,25] and not after[11,25]
    assert before[11,43] and after[11,43]
    assert report['floorUnchanged'] and report['clippedTriangles']>0
    assert A.open_sanctuary_landing(content)==report
