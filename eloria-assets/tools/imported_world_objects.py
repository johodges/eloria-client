#!/usr/bin/env python3
"""Harvest-node models that were made outside the procedural generator.

Added 2026-10-02 for Eloria Client.

`build_native_world_object_glbs.py` writes `data/world/objects.json` whole,
from the procedural catalogue in `harvestables.py`. A model made anywhere else
- the Meshy harvest nodes reviewed for the south-west isle - would be lost the
next time that generator ran, because nothing in the catalogue describes it.
This table is what describes it. The generator measures each listed GLB where
it already sits under `assets/world/harvestables/`, writes its registry entry
beside the procedural ones, and points the resource label at it when the model
answers that label.

The GLB is not written here. It is copied in, once, from the reviewed kit; the
registry records its sha256 so a file swapped in later without regenerating
the registry is caught by `tests/test_world_object_models.py` rather than
drawing a model the registry measured as something else.

Imported nodes are held to a wider triangle band than the procedural ones
(owner decision 2026-10-02, island content plan item 17): a modelled shrub
with fruit on it reads at the gameplay camera where a 424-triangle silhouette
loses its leaf cards. The generator refuses a listed GLB outside that band
before it writes anything, and the test holds the committed registry to it.

Imported nodes are also held to the procedural kit's brightness. Every
procedural node multiplies its texture by a palette colour (a baseColorFactor
of about 0.36-0.78); a model textured anywhere else has none unless it is
graded, and the first Meshy nodes drew 2-4 times brighter than the models they
replaced - chalk-white flint, white sage. Each row therefore names the
procedural model it was graded against, and the test keeps its mean surface
albedo inside `GRADE_RATIO_BAND` of that model's. The measurement needs
Pillow, so it lives with the test rather than the generator.
"""
from __future__ import annotations

import hashlib
import io
import json
import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np

#: Owner decision 2026-10-02 (island content plan, item 17): "raise it to about
#: 2,600 for imported nodes". The reviewed kits run 1,144-2,568.
IMPORTED_TRIANGLE_BAND = (90, 2600)
#: The band every procedural model, and every interactive prop, stays in.
PROCEDURAL_TRIANGLE_BAND = (90, 424)
#: An imported node's mean surface albedo over its `graded_against` model's.
#: The ungraded Meshy nodes measured 1.9-3.7 against theirs; graded, 0.8-1.5.
GRADE_RATIO_BAND = (0.4, 1.6)


@dataclass(frozen=True)
class ImportedHarvestable:
    """One harvest-node model the procedural catalogue does not author.

    `answers_label` says whether the server's resource label resolves to this
    model. A label the procedural catalogue also serves (Flint, Sage, Resin)
    is then answered by the imported model on every map, which is the global
    swap the owner chose over a per-map override; the procedural model stays
    in the registry and on disk, because map packages bake its geometry into
    their own scenery. A model that does not answer its label is registered
    and measured but drawn nowhere until it does. Flipping the flag and
    regenerating the registry is the whole of a swap, or of undoing one.

    `graded_against` is the procedural model whose brightness this one was
    graded to: the model it replaces, or for a new label the nearest like
    node.
    """
    model_id: str
    label: str
    kind: str
    tier: str
    answers_label: bool
    graded_against: str
    source: str


#: Append only. Each row's GLB is `assets/world/harvestables/<model_id>.glb`.
IMPORTED_HARVESTABLES = ()


# ---------------------------------------------------------------------------
# measuring a GLB
# ---------------------------------------------------------------------------

_FLOAT = 5126
_INDEX_TYPES = {5121: "<u1", 5123: "<u2", 5125: "<u4"}


def _read_glb(path: Path) -> tuple[dict, bytes]:
    raw = path.read_bytes()
    magic, version, _total = struct.unpack_from("<4sII", raw)
    if magic != b"glTF" or version != 2:
        raise ValueError(f"{path} is not a glTF 2 binary")
    length, kind = struct.unpack_from("<II", raw, 12)
    if kind != 0x4E4F534A:
        raise ValueError(f"{path}: first chunk is not JSON")
    document = json.loads(raw[20:20 + length].decode("utf-8"))
    binary = b""
    offset = 20 + length
    if offset + 8 <= len(raw):
        binary_length, binary_kind = struct.unpack_from("<II", raw, offset)
        if binary_kind == 0x004E4942:
            binary = raw[offset + 8:offset + 8 + binary_length]
    return document, binary


def _view(document: dict, accessor_index: int) -> tuple[dict, dict, int]:
    accessor = document["accessors"][accessor_index]
    view = document["bufferViews"][accessor["bufferView"]]
    if view.get("buffer", 0) != 0:
        raise ValueError("only the GLB's own binary chunk is supported")
    return accessor, view, view.get("byteOffset", 0) + accessor.get("byteOffset", 0)


def _floats(document: dict, binary: bytes, accessor_index: int, width: int) -> np.ndarray:
    accessor, view, start = _view(document, accessor_index)
    if accessor["componentType"] != _FLOAT:
        raise ValueError("expected a float accessor")
    stride = view.get("byteStride", 4 * width)
    rows = np.ndarray((accessor["count"], width), dtype="<f4", buffer=binary,
                      offset=start, strides=(stride, 4))
    return np.array(rows, dtype=np.float64)


def _indices(document: dict, binary: bytes, primitive: dict, count: int) -> np.ndarray:
    if "indices" not in primitive:
        return np.arange(count - count % 3, dtype=np.int64).reshape(-1, 3)
    accessor, _view_, start = _view(document, primitive["indices"])
    values = np.frombuffer(binary, dtype=_INDEX_TYPES[accessor["componentType"]],
                           count=accessor["count"], offset=start)
    return values.astype(np.int64).reshape(-1, 3)


def _local_matrix(node: dict) -> np.ndarray:
    if "matrix" in node:
        return np.array(node["matrix"], dtype=np.float64).reshape(4, 4).T
    x, y, z, w = node.get("rotation", (0.0, 0.0, 0.0, 1.0))
    rotation = np.array((
        (1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
        (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
        (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y))))
    matrix = np.identity(4)
    matrix[:3, :3] = rotation * np.array(node.get("scale", (1.0, 1.0, 1.0)))
    matrix[:3, 3] = node.get("translation", (0.0, 0.0, 0.0))
    return matrix


def drawn_primitives(document: dict):
    """(primitive, world matrix) for every primitive the default scene draws.

    A mesh the scene instances twice is yielded twice, as it draws twice.
    """
    scene = document.get("scenes", [{}])[document.get("scene", 0)]
    pending = [(index, np.identity(4)) for index in scene.get("nodes", [])]
    while pending:
        index, parent = pending.pop()
        node = document["nodes"][index]
        world = parent @ _local_matrix(node)
        pending.extend((child, world) for child in node.get("children", []))
        if "mesh" not in node:
            continue
        for primitive in document["meshes"][node["mesh"]]["primitives"]:
            if primitive.get("mode", 4) != 4:
                raise ValueError("only triangle lists are supported")
            yield primitive, world


def triangle_count(path: Path) -> int:
    """Triangles the default scene draws: the one count the registry and its
    test both use, for procedural and imported models alike."""
    document, _binary = _read_glb(path)
    total = 0
    for primitive, _world in drawn_primitives(document):
        if "indices" in primitive:
            total += document["accessors"][primitive["indices"]]["count"] // 3
        else:
            total += document["accessors"][primitive["attributes"]["POSITION"]]["count"] // 3
    return total


def measure_glb(path: Path) -> dict:
    """The registry's measurements of one GLB, taken the way the client sees it.

    Counts are summed over every primitive the default scene draws, and the
    height is the top of the posed geometry, node transforms applied, above
    the origin the client stands on the tile.
    """
    document, binary = _read_glb(path)
    vertices = 0
    alpha_tested = False
    top = -np.inf
    for primitive, world in drawn_primitives(document):
        position = primitive["attributes"]["POSITION"]
        vertices += document["accessors"][position]["count"]
        material = document.get("materials", [])[primitive["material"]] \
            if "material" in primitive else {}
        alpha_tested = alpha_tested or material.get("alphaMode") == "MASK"
        points = _floats(document, binary, position, 3)
        posed = points @ world[:3, :3].T + world[:3, 3]
        top = max(top, float(posed[:, 1].max()))
    if not np.isfinite(top):
        raise ValueError(f"{path}: the default scene draws no mesh")
    return {"vertices": int(vertices),
            "triangles": triangle_count(path),
            "alphaTested": bool(alpha_tested),
            "height": round(top, 3),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def surface_albedo(path: Path) -> float:
    """Mean linear luminance of the base colour over the drawn surface.

    Texture (sRGB decoded to linear) times baseColorFactor, sampled at seven
    points of every triangle and weighted by the triangle's area - what a
    viewer sees of the model, not the texture's unused padding. Needs Pillow.
    """
    from PIL import Image  # the generator does not need it; the test does

    document, binary = _read_glb(path)
    luma = np.array((0.2126, 0.7152, 0.0722))
    samples = np.array(((1 / 3, 1 / 3, 1 / 3), (.6, .2, .2), (.2, .6, .2), (.2, .2, .6),
                        (.45, .45, .1), (.1, .45, .45), (.45, .1, .45)))
    images: dict[int, np.ndarray] = {}
    weighted = area_total = 0.0
    for primitive, world in drawn_primitives(document):
        material = document.get("materials", [])[primitive["material"]] \
            if "material" in primitive else {}
        pbr = material.get("pbrMetallicRoughness", {})
        factor = np.array(pbr.get("baseColorFactor", (1.0, 1.0, 1.0, 1.0))[:3])
        attributes = primitive["attributes"]
        points = _floats(document, binary, attributes["POSITION"], 3)
        points = points @ world[:3, :3].T + world[:3, 3]
        triangles = _indices(document, binary, primitive, len(points))
        corners = points[triangles]
        areas = 0.5 * np.linalg.norm(np.cross(corners[:, 1] - corners[:, 0],
                                              corners[:, 2] - corners[:, 0]), axis=1)
        texture = pbr.get("baseColorTexture")
        if texture is None or "TEXCOORD_0" not in attributes:
            value = np.full(len(triangles), float(factor @ luma))
        else:
            source = document["textures"][texture["index"]]["source"]
            if source not in images:
                view = document["bufferViews"][document["images"][source]["bufferView"]]
                start = view.get("byteOffset", 0)
                pixels = Image.open(io.BytesIO(binary[start:start + view["byteLength"]]))
                srgb = np.asarray(pixels.convert("RGB"), dtype=np.float64) / 255.0
                images[source] = np.where(srgb <= 0.04045, srgb / 12.92,
                                          ((srgb + 0.055) / 1.055) ** 2.4)
            # the factor multiplies each linear channel before luminance
            plane = (images[source] * factor) @ luma
            height, width = plane.shape
            uv = _floats(document, binary, attributes["TEXCOORD_0"], 2)[triangles]
            value = np.zeros(len(triangles))
            for weights in samples:
                at = (uv * weights[None, :, None]).sum(axis=1)
                x = np.floor((at[:, 0] % 1.0) * width).astype(int).clip(0, width - 1)
                y = np.floor((at[:, 1] % 1.0) * height).astype(int).clip(0, height - 1)
                value += plane[y, x]
            value /= len(samples)
        weighted += float((value * areas).sum())
        area_total += float(areas.sum())
    return weighted / area_total


# ---------------------------------------------------------------------------
# the registry half
# ---------------------------------------------------------------------------

def check_rows(procedural_ids: set[str]) -> None:
    """Refuse a table the generator cannot honour, before it writes a file.

    An imported id may not shadow a procedural one: the generator writes the
    procedural GLB at that path and would overwrite the committed import.
    """
    seen: set[str] = set()
    for row in IMPORTED_HARVESTABLES:
        if row.model_id in procedural_ids:
            raise ValueError(f"imported model {row.model_id} shadows a procedural model")
        if row.model_id in seen:
            raise ValueError(f"imported model {row.model_id} is listed twice")
        if row.graded_against not in procedural_ids:
            raise ValueError(f"{row.model_id} is graded against {row.graded_against}, "
                             "which is not a procedural harvest model")
        seen.add(row.model_id)


def imported_entries(client_root: Path, harvestable_dir: str) -> dict[str, dict]:
    """model id -> registry entry, for every row of the table, in table order."""
    entries: dict[str, dict] = {}
    low, high = IMPORTED_TRIANGLE_BAND
    for row in IMPORTED_HARVESTABLES:
        path = client_root / harvestable_dir / f"{row.model_id}.glb"
        if not path.is_file():
            raise FileNotFoundError(
                f"{path} is listed in IMPORTED_HARVESTABLES but is not on disk; "
                "copy the reviewed GLB in before regenerating the registry")
        measured = measure_glb(path)
        if not low <= measured["triangles"] <= high:
            raise ValueError(f"{path}: {measured['triangles']} triangles is outside "
                             f"the imported band {low}-{high}")
        entries[row.model_id] = {
            "scene": f"res://{harvestable_dir}/{row.model_id}.glb",
            "label": row.label, "kind": row.kind, "tier": row.tier,
            **measured,
            "imported": True,
            "source": row.source,
        }
    return entries


def merge_imported(harvest: dict, client_root: Path, harvestable_dir: str) -> dict:
    """Add the imported models to the generator's harvestable section in place."""
    models, resources = harvest["models"], harvest["resources"]
    check_rows(set(models))
    for model_id, entry in imported_entries(client_root, harvestable_dir).items():
        models[model_id] = entry
    for row in IMPORTED_HARVESTABLES:
        if row.answers_label:
            replaced = resources.get(row.label)
            if replaced is not None:
                models[row.model_id]["replaces"] = replaced
            resources[row.label] = row.model_id
    return harvest
