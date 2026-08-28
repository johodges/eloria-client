"""Single source of truth for Amberwood's material set.

Both the runtime GLB export and the offline preview renderer are built from
this table, so what is art-directed in a preview is exactly what ships.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import gltf, textures as T


@dataclass(frozen=True)
class MaterialSpec:
    name: str
    texture: str                       # key into the generated texture set table
    roughness: float = 1.0
    metallic: float = 0.0
    base_color: tuple = (1.0, 1.0, 1.0, 1.0)
    emissive: tuple = (0.0, 0.0, 0.0)
    alpha_mode: str = "OPAQUE"
    alpha_cutoff: float = 0.45
    double_sided: bool = False
    normal_scale: float = 1.0


SPECS: tuple[MaterialSpec, ...] = (
    MaterialSpec("bark_oak", "bark_oak", roughness=1.0),
    MaterialSpec("bark_dark", "bark_dark", roughness=1.0),
    MaterialSpec("bark_pale", "bark_pale", roughness=0.98),
    MaterialSpec("foliage_amber", "foliage_amber", roughness=0.92,
                 alpha_mode="MASK", double_sided=True),
    MaterialSpec("foliage_gold", "foliage_gold", roughness=0.92,
                 alpha_mode="MASK", double_sided=True),
    MaterialSpec("foliage_rust", "foliage_rust", roughness=0.92,
                 alpha_mode="MASK", double_sided=True),
    MaterialSpec("foliage_green", "foliage_green", roughness=0.94,
                 alpha_mode="MASK", double_sided=True),
    MaterialSpec("foliage_dead", "foliage_dead", roughness=0.98,
                 alpha_mode="MASK", double_sided=True),
    MaterialSpec("undergrowth", "undergrowth", roughness=0.94,
                 alpha_mode="MASK", double_sided=True),
    MaterialSpec("timber_warm", "timber_warm", roughness=0.94),
    MaterialSpec("timber_grey", "timber_grey", roughness=0.96),
    MaterialSpec("timber_dark", "timber_dark", roughness=0.94),
    MaterialSpec("carved_wood", "carved_wood", roughness=0.90),
    MaterialSpec("shingles", "shingles", roughness=0.96),
    MaterialSpec("thatch_reed", "thatch_reed", roughness=1.0),
    MaterialSpec("ashlar", "ashlar", roughness=0.96),
    MaterialSpec("lime_plaster", "lime_plaster", roughness=0.94),
    MaterialSpec("packed_earth", "packed_earth", roughness=1.0),
    MaterialSpec("sooted_plaster", "sooted_plaster", roughness=0.97),
    MaterialSpec("charred_timber", "charred_timber", roughness=0.99),
    MaterialSpec("rubble_stone", "rubble_stone", roughness=0.98),
    MaterialSpec("cliff_rock", "cliff_rock", roughness=0.98),
    MaterialSpec("cobble_paving", "cobble_paving", roughness=0.94),
    MaterialSpec("forest_floor", "forest_floor", roughness=1.0),
    MaterialSpec("leaf_path", "leaf_path", roughness=1.0),
    MaterialSpec("shore_shingle", "shore_shingle", roughness=0.92),
    MaterialSpec("meadow_grass", "meadow_grass", roughness=1.0),
    MaterialSpec("scorched_ground", "scorched_ground", roughness=1.0),
    MaterialSpec("dark_iron", "dark_iron", roughness=0.72, metallic=1.0),
    MaterialSpec("woven_cloth", "woven_cloth", roughness=0.96, double_sided=True),
    MaterialSpec("canvas_awning", "canvas_awning", roughness=0.94, double_sided=True),
    MaterialSpec("amber_resin", "amber_resin", roughness=0.22,
                 emissive=(0.20, 0.085, 0.012)),
    MaterialSpec("amber_glass", "amber_glass", roughness=0.20,
                 emissive=(0.16, 0.070, 0.010)),
    MaterialSpec("water_sea", "water_sea", roughness=0.14,
                 base_color=(1.0, 1.0, 1.0, 0.86), alpha_mode="BLEND"),
    MaterialSpec("water_pool", "water_pool", roughness=0.18,
                 base_color=(1.0, 1.0, 1.0, 0.82), alpha_mode="BLEND"),
    MaterialSpec("water_stream", "water_stream", roughness=0.16,
                 base_color=(1.0, 1.0, 1.0, 0.78), alpha_mode="BLEND"),
    # Standing water underground: the same surface, unlit by any sky.
    MaterialSpec("water_deep", "water_pool", roughness=0.12,
                 base_color=(0.20, 0.30, 0.32, 0.90), alpha_mode="BLEND"),
)

BY_NAME = {spec.name: spec for spec in SPECS}


def build_texture_sets() -> dict[str, T.TextureSet]:
    """Generate every texture set once. Deterministic and seeded."""
    sets: dict[str, T.TextureSet] = {}
    for hue in ("oak", "dark", "pale"):
        sets[f"bark_{hue}"] = T.bark(512, seed=11 + hash(hue) % 97, hue=hue)
    for palette, seed in (("amber", 47), ("gold", 149), ("rust", 151),
                          ("green", 157), ("dead", 163)):
        sets[f"foliage_{palette}"] = T.foliage_atlas(512, seed=seed, palette=palette)
    sets["undergrowth"] = T.undergrowth_atlas(512, seed=127)
    for tone, seed in (("warm", 23), ("grey", 167), ("dark", 173)):
        sets[f"timber_{tone}"] = T.timber(512, seed=seed, tone=tone)
    sets["carved_wood"] = T.carved_wood(512, seed=29)
    sets["shingles"] = T.shingles(512, seed=37)
    sets["thatch_reed"] = T.thatch_reed(512, seed=107)
    sets["ashlar"] = T.ashlar(512, seed=53)
    sets["lime_plaster"] = T.lime_plaster(512, seed=211)
    sets["packed_earth"] = T.packed_earth(512, seed=223)
    sets["sooted_plaster"] = T.sooted_plaster(512, seed=233)
    sets["charred_timber"] = T.charred_timber(512, seed=241)
    sets["rubble_stone"] = T.rubble_stone(512, seed=61)
    sets["cliff_rock"] = T.cliff_rock(512, seed=67)
    sets["cobble_paving"] = T.cobble_paving(512, seed=83)
    sets["forest_floor"] = T.forest_floor(512, seed=71)
    sets["leaf_path"] = T.leaf_path(512, seed=79)
    sets["shore_shingle"] = T.shore_shingle(512, seed=113)
    sets["meadow_grass"] = T.meadow_grass(512, seed=131)
    sets["scorched_ground"] = T.scorched_ground(512, seed=109)
    sets["dark_iron"] = T.dark_iron(256, seed=101)
    sets["woven_cloth"] = T.woven_cloth(256, seed=103)
    sets["canvas_awning"] = T.canvas_awning(256, seed=139)
    sets["amber_resin"] = T.amber_resin(256, seed=97)
    sets["amber_glass"] = T.amber_glass(256, seed=137)
    for tone, seed in (("sea", 89), ("pool", 181), ("stream", 191)):
        sets[f"water_{tone}"] = T.water_surface(512, seed=seed, tone=tone)

    # trim the maps that do not need to ship at full resolution
    alpha_cut = {"foliage_amber", "foliage_gold", "foliage_rust", "foliage_green",
                 "foliage_dead", "undergrowth", "woven_cloth", "canvas_awning"}
    for name, texture_set in sets.items():
        texture_set.compact(orm_size=256, drop_normal=name in alpha_cut,
                            normal_size=256 if name.startswith("water") else None)
    return sets


def register_gltf_materials(builder: "gltf.GltfBuilder",
                            sets: dict[str, T.TextureSet],
                            only: set[str] | None = None) -> dict[str, int]:
    """Embed textures and register materials in the GLB.

    `only` restricts the set to the materials a package actually uses. A small
    interior that draws on a dozen materials should not carry the whole region's
    texture library: embedding all of them costs about ten megabytes of images
    nothing references.
    """
    out: dict[str, int] = {}
    for spec in SPECS:
        if only is not None and spec.name not in only:
            continue
        texture_set = sets[spec.texture]
        images = texture_set.images()
        for name, blob in images.items():
            builder.add_image(name, blob)
        out[spec.name] = builder.add_material(gltf.Material(
            name=spec.name,
            base_color=spec.base_color,
            metallic=spec.metallic,
            roughness=spec.roughness,
            base_color_texture=f"{spec.texture}_basecolor",
            orm_texture=f"{spec.texture}_orm",
            normal_texture=(f"{spec.texture}_normal"
                            if f"{spec.texture}_normal" in images else None),
            normal_scale=spec.normal_scale,
            emissive=spec.emissive,
            alpha_mode=spec.alpha_mode,
            alpha_cutoff=spec.alpha_cutoff,
            double_sided=spec.double_sided))
    return out


def register_preview_materials(scene, sets: dict[str, T.TextureSet]) -> None:
    """Mirror the same table into the offline preview renderer."""
    from .render import RenderMaterial
    for spec in SPECS:
        texture_set = sets[spec.texture]
        alpha = texture_set.alpha
        if alpha is None:
            alpha = np.full(texture_set.base_color.shape[:2], 255, np.uint8)
        scene.add_texture(spec.texture + "_albedo",
                          np.dstack([texture_set.base_color, alpha]))
        scene.add_texture(spec.texture + "_orm",
                          np.dstack([texture_set.orm,
                                     np.full(texture_set.orm.shape[:2], 255, np.uint8)]))
        scene.add_material(RenderMaterial(
            name=spec.name,
            base_color=spec.base_color,
            roughness=spec.roughness,
            metallic=spec.metallic,
            emissive=spec.emissive,
            albedo=spec.texture + "_albedo",
            orm=spec.texture + "_orm",
            alpha_mode=spec.alpha_mode,
            alpha_cutoff=spec.alpha_cutoff,
            double_sided=spec.double_sided))
