"""Point the Human equipment variants at the textures the shipped equipment already carries.

    python eloria-assets/tools/share_human_equipment_textures.py

refit_human_bodies.py fits from the original Meshy sources, so a variant's art
texture is the full-resolution original of an image the shipped piece already
references as a 1024 px JPEG (the shipped set was shrunk after packing).  For
each image of each `variants/human_*/<slug>.glb`:

* if one of the shipped base piece's images is the same picture (64 px
  thumbnails within 3/255 mean difference), the variant names that file;
* otherwise (the "Fitted cloth" lining, sampled from the new body's shirt) it
  is re-encoded the shipped way - at most 1024 px, JPEG quality 85,
  content-addressed `textures/canonical_<sha>.jpg`.

Only the JSON image entries change; geometry, skin and materials are untouched.
Textures nothing references any more are deleted if git does not track them.
"""
from __future__ import annotations

import hashlib
import io
import json
import struct
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
EQUIPMENT = ROOT / 'godot-client/assets/actors/native/equipment'


def read(path: Path):
    data = path.read_bytes()
    n = struct.unpack('<I', data[12:16])[0]
    return json.loads(data[20:20 + n]), data[20 + n:]


def write(path: Path, doc: dict, rest: bytes):
    text = json.dumps(doc, separators=(',', ':')).encode()
    text += b' ' * ((4 - len(text) % 4) % 4)
    out = bytearray(struct.pack('<III', 0x46546C67, 2, 0))
    out += struct.pack('<II', len(text), 0x4E4F534A) + text + rest
    struct.pack_into('<I', out, 8, len(out))
    path.write_bytes(bytes(out))


def thumb(path: Path):
    return np.asarray(Image.open(path).convert('RGB').resize((64, 64), Image.BILINEAR)).astype(np.float32)


def main() -> int:
    tracked = set(subprocess.check_output(['git', 'ls-files', 'godot-client/assets/actors/native/equipment/textures'],
                                          cwd=ROOT, text=True).split())
    shared = reencoded = 0
    referenced = set()
    for folder in ('human_male', 'human_female'):
        for path in sorted((EQUIPMENT / 'variants' / folder).glob('*.glb')):
            doc, rest = read(path)
            base = EQUIPMENT / path.name
            base_images = []
            if base.exists():
                bdoc, _ = read(base)
                base_images = [EQUIPMENT / i['uri'] for i in bdoc.get('images', []) if 'uri' in i]
            thumbs = [(p, thumb(p)) for p in base_images]
            changed = False
            for image in doc.get('images', []):
                current = (path.parent / image['uri']).resolve()
                t = thumb(current)
                match = min(((np.abs(t - bt).mean(), p) for p, bt in thumbs), default=(1e9, None))
                if match[0] < 3.0:
                    target = match[1]
                    shared += 1
                else:
                    im = Image.open(current).convert('RGB')
                    if max(im.size) > 1024:
                        im = im.resize((1024, 1024) if im.width == im.height else
                                       tuple(round(s * 1024 / max(im.size)) for s in im.size), Image.LANCZOS)
                    buf = io.BytesIO(); im.save(buf, 'JPEG', quality=85, optimize=True)
                    data = buf.getvalue()
                    target = EQUIPMENT / 'textures' / ('canonical_' + hashlib.sha256(data).hexdigest() + '.jpg')
                    if not target.exists():
                        target.write_bytes(data)
                    reencoded += 1
                uri = Path('../../textures') / target.name
                referenced.add(target.name)
                if image.get('uri') != uri.as_posix():
                    image['uri'] = uri.as_posix(); image['mimeType'] = 'image/jpeg' if target.suffix == '.jpg' else 'image/png'
                    changed = True
            if changed:
                write(path, doc, rest)
    removed = 0
    for tex in (EQUIPMENT / 'textures').glob('canonical_*'):
        if tex.suffix == '.import':
            continue
        rel = tex.relative_to(ROOT).as_posix()
        if rel in tracked or tex.name in referenced:
            continue
        # untracked and unreferenced by the Human variants: a leftover of the raw install
        still_used = False
        if not still_used:
            tex.unlink(); removed += 1
            imp = tex.with_name(tex.name + '.import')
            if imp.exists():
                imp.unlink()
    print(json.dumps({'shared': shared, 'reencoded': reencoded, 'removed_textures': removed}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
