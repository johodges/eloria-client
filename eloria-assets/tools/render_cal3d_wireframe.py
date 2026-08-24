#!/usr/bin/env python3
"""Render a deterministic isometric wireframe from a Cal3D XML mesh."""
from __future__ import annotations

import argparse
from pathlib import Path
import xml.etree.ElementTree as ET

from generate_bootstrap_pack import png
from render_e3d_wireframe import line


def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument('mesh',type=Path); parser.add_argument('output',type=Path)
    args=parser.parse_args(); lines=args.mesh.read_text().splitlines()
    if not lines or 'MAGIC="XMF"' not in lines[0]: raise ValueError(f'not a Cal3D XML mesh: {args.mesh}')
    submesh=ET.fromstring('\n'.join(lines[1:])).find('SUBMESH')
    vertices={int(v.attrib['ID']):tuple(map(float,v.findtext('POS').split())) for v in submesh.findall('VERTEX')}
    projected={i:(x-y*.55,z+(x+y)*.16) for i,(x,y,z) in vertices.items()}
    min_x=min(x for x,_ in projected.values()); max_x=max(x for x,_ in projected.values())
    min_y=min(y for _,y in projected.values()); max_y=max(y for _,y in projected.values())
    scale=min(440/max(.01,max_x-min_x),440/max(.01,max_y-min_y))
    screen={i:(int(36+(x-min_x)*scale),int(476-(y-min_y)*scale)) for i,(x,y) in projected.items()}
    pixels=set()
    for face in submesh.findall('FACE'):
        a,b,c=(screen[int(i)] for i in face.attrib['VERTEXID'].split())
        line(pixels,*a,*b); line(pixels,*b,*c); line(pixels,*c,*a)
    png(args.output,512,512,lambda x,y:(116,216,205,255) if (x,y) in pixels else
        (40+((x//32+y//32)&1)*4,50+((x//32+y//32)&1)*4,51,255))


if __name__=='__main__': main()
