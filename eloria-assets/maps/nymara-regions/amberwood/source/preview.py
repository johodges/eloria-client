"""Shared preview harness: build a Scene with the full Amberwood material set."""
import sys, os, pickle, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from amberwood import materials as MAT, render as R

_CACHE = "/tmp/amberwood_textures.pkl"


def texture_sets(force: bool = False):
    if not force and os.path.exists(_CACHE):
        with open(_CACHE, "rb") as handle:
            return pickle.load(handle)
    t = time.time()
    sets = MAT.build_texture_sets()
    with open(_CACHE, "wb") as handle:
        pickle.dump(sets, handle)
    print(f"[textures] generated {len(sets)} sets in {time.time() - t:.1f}s")
    return sets


def new_scene(sets=None):
    scene = R.Scene()
    MAT.register_preview_materials(scene, sets or texture_sets())
    return scene


def scene_from_build(build, sets=None, include_kinds=None):
    """Fill a preview Scene from a RegionBuild (same materials as the GLB)."""
    from amberwood import mesh as M
    scene = new_scene(sets)
    for name, piece in build.terrain_meshes.items():
        scene.add_mesh(piece)
    for name, piece in build.water_meshes.items():
        scene.add_mesh(piece)
    for placement in build.placements:
        if include_kinds is not None and placement.kind not in include_kinds:
            continue
        transform = (M.translation(*placement.position)
                     @ M.rotation_y(placement.rotation_y)
                     @ M.scaling(placement.scale))
        target = build.meshes[placement.mesh]
        parts = getattr(target, "parts", None)
        if parts:
            for part in parts:
                scene.add_mesh(part, transform)
        else:
            scene.add_mesh(target, transform)
    return scene
