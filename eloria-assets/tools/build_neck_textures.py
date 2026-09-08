"""Rebake canonical neck UVs from actual neck skin, without repeating faces.

Sources are the original canonical full bodies before the shared-body graft.
The installed GLBs supply the current neck atlas dimensions and exact head
boundary colours; their geometry and source atlases are never modified.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image
import shared_player_bodies as sb
from build_face_masks import g, source_image


def bake(model_path, source_path):
    d, b = g.read(model_path)
    sd, source_binary = sb.ea.read_glb(source_path)
    source = sb.block(sd, source_binary)
    body = next(m for m in d['meshes'] if m['name'] == 'body')
    surface, part = next((i, p) for i, p in enumerate(body['primitives'])
                         if p.get('extras', {}).get('sourceRole') == 'neck_join')
    previous = source_image(d, b, part['material'])
    _, pixels = sb.material_image(sd, source_binary, sb.body_material(source))
    world = sb.ea.global_matrices(sd)
    origin = world[next(i for i, n in enumerate(sd['nodes']) if n.get('name') == 'neck_01')][:3, 3]
    head = world[next(i for i, n in enumerate(sd['nodes']) if n.get('name') == 'Head')][:3, 3]
    axis = (head-origin)/np.linalg.norm(head-origin)
    side = np.cross(axis, [1., 0., 0.])
    height, width = previous.shape[:2]
    yy, xx = np.mgrid[:height, :width]
    theta = ((xx+.5)/width-.5)*2*np.pi
    h = -.160+(yy+.5)/height*(sb.UPPER_CUT+.160)
    points = (origin+h[..., None]*axis+.055*(np.cos(theta)[..., None]*[1., 0., 0.]
              +np.sin(theta)[..., None]*side)).reshape(-1, 3)
    colours = np.concatenate([sb.project_neck_texture(source, pixels, points[i:i+4096],
                              origin, axis, extend=True) for i in range(0, len(points), 4096)])
    colours = colours.reshape(height, width, 3)
    # Meet the actual retained cut contour once, at the top. The old atlas's
    # last row already samples that contour. Do not retain its repeated rows.
    fade = np.clip((h-(sb.UPPER_CUT-.006))/.006, 0, 1)[..., None]
    fade = fade*fade*(3-2*fade)
    colours = colours*(1-fade) + previous[-1:]/255.*fade
    atlas = np.rint(np.clip(colours, 0, 1)*255).astype('u1')
    atlas[-1] = previous[-1]
    return atlas, {'surface': surface,
                   'modelSHA256': hashlib.sha256(model_path.read_bytes()).hexdigest(),
                   'sourceSHA256': hashlib.sha256(source_path.read_bytes()).hexdigest(),
                   'projection': 'monotonic source neck below head cut'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models', type=Path, required=True)
    parser.add_argument('--sources', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    reports = {}
    for source in sorted(args.sources.glob('*.glb')):
        pixels, report = bake(args.models/source.name, source)
        target = args.out/(source.stem+'.png')
        Image.fromarray(pixels).save(target, optimize=True)
        report['textureSHA256'] = hashlib.sha256(target.read_bytes()).hexdigest()
        reports[source.stem] = report
        print(source.stem, 'neck rebaked', flush=True)
    (args.out/'manifest.json').write_text(json.dumps(reports, indent=2)+'\n')


if __name__ == '__main__':
    main()
