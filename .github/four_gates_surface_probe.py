#!/usr/bin/env python3
import json
import math
import struct
import sys
from pathlib import Path

GLB_PATH = Path("eloria-assets/maps/four-gates-city/four-gates-city.glb")
OUT_PATH = Path("godot-client/test-artifacts/surface-probe/four-gates-surface.json")
POINT_X = 178.8372
POINT_Z = -44.88372


def mat_identity():
    return [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]


def mat_mul(a, b):
    return [[sum(a[r][k] * b[k][c] for k in range(4)) for c in range(4)] for r in range(4)]


def mat_apply(m, p):
    x, y, z = p
    return (
        m[0][0] * x + m[0][1] * y + m[0][2] * z + m[0][3],
        m[1][0] * x + m[1][1] * y + m[1][2] * z + m[1][3],
        m[2][0] * x + m[2][1] * y + m[2][2] * z + m[2][3],
    )


def node_matrix(node):
    if "matrix" in node:
        values = node["matrix"]
        return [[float(values[c * 4 + r]) for c in range(4)] for r in range(4)]
    tx, ty, tz = [float(v) for v in node.get("translation", [0, 0, 0])]
    sx, sy, sz = [float(v) for v in node.get("scale", [1, 1, 1])]
    x, y, z, w = [float(v) for v in node.get("rotation", [0, 0, 0, 1])]
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    r = [
        [1 - 2 * (yy + zz), 2 * (xy - wz), 2 * (xz + wy), 0],
        [2 * (xy + wz), 1 - 2 * (xx + zz), 2 * (yz - wx), 0],
        [2 * (xz - wy), 2 * (yz + wx), 1 - 2 * (xx + yy), 0],
        [0, 0, 0, 1],
    ]
    s = [[sx, 0, 0, 0], [0, sy, 0, 0], [0, 0, sz, 0], [0, 0, 0, 1]]
    t = mat_identity()
    t[0][3], t[1][3], t[2][3] = tx, ty, tz
    return mat_mul(t, mat_mul(r, s))


def parse_glb(path):
    raw = path.read_bytes()
    magic, version, total_len = struct.unpack_from("<4sII", raw, 0)
    if magic != b"glTF" or version != 2 or total_len != len(raw):
        raise RuntimeError("invalid GLB header")
    offset = 12
    gltf = None
    binary = None
    while offset + 8 <= len(raw):
        chunk_len, chunk_type = struct.unpack_from("<II", raw, offset)
        offset += 8
        chunk = raw[offset:offset + chunk_len]
        offset += chunk_len
        if chunk_type == 0x4E4F534A:
            gltf = json.loads(chunk.decode("utf-8").rstrip("\x00 \t\r\n"))
        elif chunk_type == 0x004E4942:
            binary = chunk
    if gltf is None or binary is None:
        raise RuntimeError("GLB missing JSON or BIN chunk")
    return gltf, binary


COMPONENTS = {
    5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2), 5123: ("H", 2),
    5125: ("I", 4), 5126: ("f", 4),
}
TYPE_COUNTS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}


def accessor_values(gltf, binary, accessor_index):
    acc = gltf["accessors"][accessor_index]
    if "bufferView" not in acc:
        raise RuntimeError(f"accessor {accessor_index} has no bufferView")
    view = gltf["bufferViews"][acc["bufferView"]]
    fmt, component_size = COMPONENTS[acc["componentType"]]
    component_count = TYPE_COUNTS[acc["type"]]
    packed_size = component_size * component_count
    stride = int(view.get("byteStride", packed_size))
    base = int(view.get("byteOffset", 0)) + int(acc.get("byteOffset", 0))
    out = []
    unpack_fmt = "<" + fmt * component_count
    for i in range(int(acc["count"])):
        values = struct.unpack_from(unpack_fmt, binary, base + i * stride)
        out.append(values[0] if component_count == 1 else values)
    return out


def projected_hit_y(p0, p1, p2, x, z, eps=1.0e-6):
    x0, y0, z0 = p0
    x1, y1, z1 = p1
    x2, y2, z2 = p2
    denom = (z1 - z2) * (x0 - x2) + (x2 - x1) * (z0 - z2)
    if abs(denom) < eps:
        return None
    a = ((z1 - z2) * (x - x2) + (x2 - x1) * (z - z2)) / denom
    b = ((z2 - z0) * (x - x2) + (x0 - x2) * (z - z2)) / denom
    c = 1.0 - a - b
    if a < -eps or b < -eps or c < -eps or a > 1 + eps or b > 1 + eps or c > 1 + eps:
        return None
    return a * y0 + b * y1 + c * y2


def triangle_normal_y(p0, p1, p2):
    ax, ay, az = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
    bx, by, bz = p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]
    nx = ay * bz - az * by
    ny = az * bx - ax * bz
    nz = ax * by - ay * bx
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    return 0.0 if length < 1.0e-9 else ny / length


def main():
    gltf, binary = parse_glb(GLB_PATH)
    nodes = gltf.get("nodes", [])
    meshes = gltf.get("meshes", [])
    parents = {}
    for parent_index, node in enumerate(nodes):
        for child in node.get("children", []):
            parents[int(child)] = parent_index

    local = [node_matrix(node) for node in nodes]
    world_cache = {}

    def world_matrix(i):
        if i in world_cache:
            return world_cache[i]
        p = parents.get(i)
        result = local[i] if p is None else mat_mul(world_matrix(p), local[i])
        world_cache[i] = result
        return result

    hits = []
    containing = []
    mesh_nodes = 0
    triangle_count = 0
    for node_index, node in enumerate(nodes):
        if "mesh" not in node:
            continue
        mesh_nodes += 1
        mesh_index = int(node["mesh"])
        mesh = meshes[mesh_index]
        matrix = world_matrix(node_index)
        node_name = node.get("name", f"node_{node_index}")
        all_points = []
        for primitive_index, primitive in enumerate(mesh.get("primitives", [])):
            if int(primitive.get("mode", 4)) != 4:
                continue
            attrs = primitive.get("attributes", {})
            if "POSITION" not in attrs:
                continue
            raw_positions = accessor_values(gltf, binary, int(attrs["POSITION"]))
            positions = [mat_apply(matrix, p) for p in raw_positions]
            all_points.extend(positions)
            if "indices" in primitive:
                indices = [int(v) for v in accessor_values(gltf, binary, int(primitive["indices"]))]
            else:
                indices = list(range(len(positions)))
            for tri_start in range(0, len(indices) - 2, 3):
                triangle_count += 1
                try:
                    p0 = positions[indices[tri_start]]
                    p1 = positions[indices[tri_start + 1]]
                    p2 = positions[indices[tri_start + 2]]
                except IndexError:
                    continue
                y = projected_hit_y(p0, p1, p2, POINT_X, POINT_Z)
                if y is None:
                    continue
                hits.append({
                    "node": node_name,
                    "node_index": node_index,
                    "mesh": mesh.get("name", f"mesh_{mesh_index}"),
                    "primitive": primitive_index,
                    "triangle": tri_start // 3,
                    "y": y,
                    "normal_y": triangle_normal_y(p0, p1, p2),
                })
        if all_points:
            min_x = min(p[0] for p in all_points); max_x = max(p[0] for p in all_points)
            min_y = min(p[1] for p in all_points); max_y = max(p[1] for p in all_points)
            min_z = min(p[2] for p in all_points); max_z = max(p[2] for p in all_points)
            if min_x - 1e-6 <= POINT_X <= max_x + 1e-6 and min_z - 1e-6 <= POINT_Z <= max_z + 1e-6:
                containing.append({"node": node_name, "min": [min_x, min_y, min_z], "max": [max_x, max_y, max_z]})

    hits.sort(key=lambda h: h["y"], reverse=True)
    horizontal = [h for h in hits if abs(h["normal_y"]) >= 0.35]
    result = {
        "point": [POINT_X, POINT_Z],
        "navmesh_y": 31.0,
        "mesh_nodes_scanned": mesh_nodes,
        "triangles_scanned": triangle_count,
        "hits": hits[:50],
        "horizontal_hits": horizontal[:30],
        "nodes_containing_xz": sorted(containing, key=lambda v: v["max"][1], reverse=True)[:80],
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    if not hits:
        print("ERROR: no rendered triangle intersects live actor X/Z", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
