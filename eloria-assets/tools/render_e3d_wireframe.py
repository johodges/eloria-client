#!/usr/bin/env python3
"""Render a deterministic isometric wireframe preview of a native E3D mesh."""
from __future__ import annotations

import argparse
from pathlib import Path
import struct

from generate_bootstrap_pack import png


def line(points: set[tuple[int, int]], x0: int, y0: int, x1: int, y1: int) -> None:
    dx, dy = abs(x1-x0), -abs(y1-y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    error = dx + dy
    while True:
        points.add((x0, y0))
        if x0 == x1 and y0 == y1:
            return
        twice = 2 * error
        if twice >= dy:
            error += dy
            x0 += sx
        if twice <= dx:
            error += dx
            y0 += sy


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mesh", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    data = args.mesh.read_bytes()
    if data[:4] != b"e3dx":
        raise ValueError(f"not an E3D mesh: {args.mesh}")
    vertices, vertex_size, vertex_offset, indices, index_size, index_offset = \
        struct.unpack_from("<6i", data, 28)
    if vertex_size != 32 or index_size != 2 or indices % 3:
        raise ValueError(f"unsupported E3D layout: {args.mesh}")
    positions = [struct.unpack_from("<3f", data, vertex_offset+i*vertex_size+20)
                 for i in range(vertices)]
    faces = struct.unpack_from(f"<{indices}H", data, index_offset)
    projected = [(x-y*.55, z+(x+y)*.16) for x, y, z in positions]
    min_x=min(x for x,_ in projected); max_x=max(x for x,_ in projected)
    min_y=min(y for _,y in projected); max_y=max(y for _,y in projected)
    scale=min(440/max(.01,max_x-min_x),440/max(.01,max_y-min_y))
    screen=[(int(36+(x-min_x)*scale),int(476-(y-min_y)*scale)) for x,y in projected]
    pixels=set()
    for index in range(0, indices, 3):
        a,b,c=(screen[faces[index+j]] for j in range(3))
        line(pixels,*a,*b); line(pixels,*b,*c); line(pixels,*c,*a)
    png(args.output,512,512,
        lambda x,y:(221,202,145,255) if (x,y) in pixels else
                   (43+((x//32+y//32)&1)*4,54+((x//32+y//32)&1)*4,54,255))


if __name__ == "__main__":
    main()
