"""Geometry regressions for the visible back-of-shirt and scalp failures."""
import json
import hashlib
import os
from pathlib import Path
import sys
import unittest

import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[2]
CLIENT = ROOT / 'godot-client'
sys.path.insert(0, str(ROOT / 'eloria-assets/tools'))
import equipment_authoring as ea
from verify_shared_player_bodies import primitives


def mesh_for(document, binary, name):
    vertices, faces = [], []
    offset = 0
    for surface, _, a, f in primitives(document, binary):
        if surface != name:
            continue
        vertices.append(a['POSITION'])
        faces.append(f + offset)
        offset += len(a['POSITION'])
    return trimesh.Trimesh(np.concatenate(vertices), np.concatenate(faces), process=False)


class CharacterAppearanceFitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models = json.loads((CLIENT / 'data/actors/models.json').read_text())['models']
        cls.models = {k:v for k,v in cls.models.items() if 'bodyTemplate' in v}
        candidate = os.environ.get('ELORIA_APPEARANCE_CANDIDATES')
        if candidate:
            for slug,config in cls.models.items():
                config.update(json.loads((Path(candidate)/(slug+'.config.json')).read_text()))
                config['scene'] = str(Path(candidate)/(slug+'.glb'))

    def test_back_shirt_covers_neck_without_shader_grow(self):
        # Independent camera rays through the actual reported tear region.
        rays = np.array([[x,y,-.5] for x in np.linspace(-.035,.035,11)
                         for y in np.linspace(1.36,1.49,20)])
        directions = np.tile([0.,0.,1.], (len(rays),1))
        for slug, config in self.models.items():
            with self.subTest(model=slug):
                d,b = ea.read_glb(CLIENT / config['scene'].removeprefix('res://'))
                depths = {}
                for name in ('body','wardrobe_shirt'):
                    mesh = mesh_for(d,b,name)
                    locations, indices, _ = mesh.ray.intersects_location(rays,directions,multiple_hits=False)
                    depth = np.full(len(rays),np.inf)
                    depth[indices] = locations[:,2]
                    depths[name] = depth
                hit = np.isfinite(depths['body'])
                # All races share the approved source body: its open neckline
                # and clothing form one shell rather than overlapping torsos.
                self.assertTrue(np.isfinite(np.minimum(depths['body'], depths['wardrobe_shirt'])).all())
                self.assertGreater(hit.sum(), 50)
                self.assertGreater(float((depths['body'][hit]-depths['wardrobe_shirt'][hit]).min()), .002)
                self.assertIn('wardrobe_shirt',config['wardrobeBakedGrow'])

    def test_skin_calibration_matches_the_installed_source_materials(self):
        # Replacing a source head must not silently reuse the previous head's
        # calibration: that would bring back wrong colors and neck seams.
        for slug, config in self.models.items():
            with self.subTest(model=slug):
                path = CLIENT / config['scene'].removeprefix('res://')
                palette = config['skinPalette']
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), palette['sourceSHA256'])
                document, _ = ea.read_glb(path)
                refs = palette['references']
                face = refs['body'][config['faceAppearance']['sourceSurface']]
                for mesh in document['meshes']:
                    if mesh['name'] not in ('body', 'eyes', 'eyebrows', 'scalp'):
                        continue
                    values = refs[mesh['name']]
                    self.assertEqual(len(mesh['primitives']), len(values))
                    self.assertTrue(np.isfinite(values).all())
                    self.assertTrue((np.asarray(values) > 0).all())
                    self.assertTrue((np.asarray(values) <= 1).all())
                    if mesh['name'] != 'body':
                        self.assertTrue(all(value == face for value in values))

    def test_hair_uses_the_body_bind_pose_and_has_a_closed_crown(self):
        for slug, config in self.models.items():
            body, bb = ea.read_glb(CLIENT / config['scene'].removeprefix('res://'))
            skeleton = body['skins'][0]
            bones = [body['nodes'][i]['name'] for i in skeleton['joints']]
            binds = ea.accessor_array(body,bb,skeleton['inverseBindMatrices'])
            with self.subTest(model=slug):
                self.assertTrue(config['hairSkinned'])
                self.assertEqual({},config['hairFit'])
                self.assertEqual(10,len(config['hairStyles']))
            for style in range(1,10):
                with self.subTest(model=slug,style=style):
                    d,b = ea.read_glb(CLIENT / config['hairStyles'][style].removeprefix('res://'))
                    skin = d['skins'][0]
                    self.assertEqual(bones,[d['nodes'][i]['name'] for i in skin['joints']])
                    np.testing.assert_array_equal(binds,ea.accessor_array(d,b,skin['inverseBindMatrices']))
                    for _,_,a,f in primitives(d,b):
                        ids = np.unique(f)
                        self.assertTrue(np.isfinite(a['POSITION'][ids]).all())
                        self.assertTrue((a['WEIGHTS_0'][ids]>=0).all())
                        np.testing.assert_allclose(a['WEIGHTS_0'][ids].sum(1),1,atol=2e-6)
                        self.assertLess(int(a['JOINTS_0'][ids].max()),len(bones))
                    # Five rays at the top centre must hit the coiffure above
                    # the bald scalp. Horns and side crystals are outside this
                    # central patch and remain free to protrude through hair.
                    scalp = mesh_for(body,bb,'scalp')
                    hair = mesh_for(d,b,d['meshes'][0]['name'])
                    origins=np.array([[x,2.,z] for x,z in [(0,0),(-.012,0),(.012,0),(0,-.012),(0,.012)]])
                    direction=np.tile([0.,-1.,0.],(len(origins),1))
                    hs,ri,_=scalp.ray.intersects_location(origins,direction,multiple_hits=False)
                    hh,rh,_=hair.ray.intersects_location(origins,direction,multiple_hits=False)
                    sd=dict(zip(ri,hs[:,1]));hd=dict(zip(rh,hh[:,1]))
                    self.assertGreaterEqual(len(sd),3)
                    self.assertTrue(set(sd)<=set(hd))
                    for ray,height in sd.items():
                        if not config.get('hairAllowsProtrusions'):
                            self.assertGreater(hd[ray]-height,.001)
                        else:
                            # Crystals and horns remain exposed through a
                            # closed coiffure instead of stretching it to tips.
                            self.assertGreater(hd[ray],1.64)


if __name__=='__main__':
    unittest.main()
