"""Reapply server-owned marker tiles after deterministic region builds."""
import glb_reader as G
from verify_runtime import VerticalRayIndex

def apply(manifest, package, posts):
    document, body = G.load(package / "world.glb")
    selected = G.named(document, "Terrain_") + G.named(document, "Walk_")
    ground = VerticalRayIndex(G.triangles(document, body, selected), cell=4)
    transform = manifest["coordinateTransform"]
    ox, oy = transform["serverOrigin"]
    metres = transform["metresPerTile"]
    for bucket, entries in posts.items():
        for entry in manifest.get(bucket, []):
            tile = entries.get(entry.get("id"))
            if tile is None:
                continue
            x, z = (tile[0]-ox)*metres, -(tile[1]-oy)*metres
            height = ground.top_hit(x, z)
            if height is None:
                raise ValueError(f"{entry['id']}: no standing surface at {tile}")
            entry["serverTile"] = list(tile)
            entry["position"] = [round(x, 2), round(height, 2), round(z, 2)]
