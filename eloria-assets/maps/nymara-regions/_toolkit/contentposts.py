"""Reapply server-owned marker tiles after deterministic region builds."""
import glb_reader as G
from verify_runtime import VerticalRayIndex

def apply(manifest, package, posts, glb_name="world.glb"):
    document, body = G.load(package / glb_name)
    selected = G.named(document, "Terrain_") + G.named(document, "Walk_")
    ground = VerticalRayIndex(G.triangles(document, body, selected), cell=4)
    transform = manifest["coordinateTransform"]
    ox, oy = transform["serverOrigin"]
    metres = transform["metresPerTile"]
    for bucket, entries in posts.items():
        target = manifest
        for part in bucket.split("."):
            target = target.get(part, {})
        for entry in target if isinstance(target,list) else []:
            tile = entries.get(entry.get("id"))
            if tile is None:
                continue
            x, z = (tile[0]-ox)*metres, -(tile[1]-oy)*metres
            height = ground.top_hit(x, z)
            if height is None:
                raise ValueError(f"{entry['id']}: no standing surface at {tile}")
            entry["serverTile"] = list(tile)
            field = "center" if "center" in entry else "position"
            entry[field] = [round(x, 2), round(height, 2), round(z, 2)]
