#!/usr/bin/env python3
"""Build the VRAM-compressed sidecars of the content-addressed map images.

    python godot-client/tools/build_vram_textures.py                 # every map, in place
    python godot-client/tools/build_vram_textures.py --out-root DIR  # into a package stage

Map packages name their shared images by URI and list each one with its
sha256 in the manifest's externalResources. The client used to decode every
one of them to RGBA8 on the GPU (4 bytes a pixel, plus a third for mips). This
tool writes, beside each directory of such images, a vram/ folder:

  vram/<sha256>.<recipe>.evt   16-byte header ('EVT1', raw DDS size, flags with
                               bit0 = zstd, reserved) + one zstd frame (level
                               19) holding a DDS with the full mip chain,
                               already block compressed
  vram/index.json              schema, recipeVersion, encoder, and per source
                               sha: file, recipe, format, width, height,
                               mipmaps, gpuBytes, rawBytes, fileBytes, sha256,
                               roles; plus every excluded sha with its reason
  vram/report.json             the per-image quality numbers (not shipped)

The client (src/world/vram_textures.gd) uploads a sidecar as it is when the
renderer can sample its format, and decodes the JPEG/PNG otherwise. Nothing
here changes a map package: manifests, GLBs and digests are untouched, and a
sidecar is keyed by the source's own sha.

Recipes, from every glTF material slot that samples the image in any map:

  base        base colour / emissive, alpha unused  -> BC7 (sRGB view)
  base_alpha  base colour of a MASK/BLEND material whose alpha is used -> BC7
  orm         metallicRoughness and/or occlusion     -> BC1
  orm_bc7     an ORM map below its floor as BC1      -> BC7 (one second chance:
              BC1 shares endpoints across channels that ORM keeps unrelated)
  normal      normalTexture                          -> BC5 (Godot rebuilds Z)

`roles` lists every slot the encode was chosen for, as the client names them
(base, base_cutout for a base colour in a MASK/BLEND material, emissive,
normal, orm, occlusion). The client uses a sidecar only where the map it is
loading samples the image in those roles, so an index left over from before a
content change (a base colour that became a cutout, an ORM map now sampled as
colour) makes that image decode instead of rendering wrong.

Excluded (the client decodes them as before): an image used in two
incompatible roles (role_conflict), one no material samples
(no_material_role), a size that is not a multiple of 4, and any encode below
its quality floor:

  base / base_alpha  PSNR >= 36 dB (RGB, mip 0); alpha flips at 0.5 <= 1.0 %
                     at mip 0 and <= 1.5 % at mip 2
  normal             angular error mean <= 1.0 deg, p99 <= 3 deg (Z rebuilt)
  orm                PSNR >= 33 dB per channel

Encoding runs headless on the Godot 4.7.2 EDITOR binary (tools/vram_encode.gd)
in --procs processes; the export templates cannot encode. The mip chain is
Image.generate_mipmaps() on the decoded image, as the client builds it.

Encodes are cached by (source sha, recipe, recipe version, Godot version),
never by output: BC7 output is not bit-for-bit reproducible. The cache must be
a directory git ignores (the default, <repo>/.vram-encode-cache, is); entries
this run did not use are pruned unless --no-prune.

Needs numpy and Pillow (the quality check decodes the DDS with Pillow).
"""
from __future__ import annotations

import argparse
import concurrent.futures as futures
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

CLIENT = Path(__file__).resolve().parents[1]
REPO = CLIENT.parent
PROJECT = REPO.parent
ENCODER = CLIENT / "tools" / "vram_encode.gd"
GODOT_EXE = "Godot_v4.7.2-stable_win64_console.exe"

SCHEMA = 1
# Raise when a recipe's encode changes (a different compressor call, channel
# set or mip rule): it is part of every cache key, so nothing old is reused,
# and the client refuses an index whose recipeVersion it does not know.
RECIPE_VERSION = 1
CONTAINER = "EVT1 header + zstd(19) DDS with the full mip chain"
SIDECAR_DIR = "vram"
HEADER = struct.Struct("<4sIII")
FLAG_ZSTD = 1

SLOTS = {"baseColorTexture": "base", "emissiveTexture": "emissive", "normalTexture": "normal",
         "metallicRoughnessTexture": "orm", "occlusionTexture": "occlusion"}
FORMAT_OF = {"base": "bc7", "base_alpha": "bc7", "orm": "bc1", "orm_bc7": "bc7", "normal": "bc5"}
SECOND_CHANCE = {"orm": "orm_bc7"}
FLOORS = {"base_psnr": 36.0, "base_psnr_median": 42.0, "alpha_flip_mip0": 0.010,
          "alpha_flip_mip2": 0.015, "normal_mean_deg": 1.0, "normal_p99_deg": 3.0,
          "orm_psnr": 33.0}
DDS_BLOCK_BYTES = {"bc1": 8, "bc5": 16, "bc7": 16}
PILLOW_BCN = {"bc1": ("RGBA", 1), "bc5": ("RGB", 5), "bc7": ("RGBA", 7)}


class BuildError(RuntimeError):
    pass


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


# --- inventory -----------------------------------------------------------------

def glb_json(path: Path) -> dict:
    with open(path, "rb") as handle:
        header = handle.read(20)
        if len(header) < 20 or header[:4] != b"glTF":
            raise ValueError("not a GLB")
        length = struct.unpack_from("<I", header, 12)[0]
        return json.loads(handle.read(length).decode("utf-8"))


def image_roles(document: dict) -> dict[int, set[tuple[str, str]]]:
    """glTF image index -> {(role, alphaMode)} over every material slot."""
    sources = []
    for texture in document.get("textures", []):
        source = texture.get("source")
        for extension in (texture.get("extensions") or {}).values():
            if isinstance(extension, dict) and "source" in extension:
                source = extension["source"]
        sources.append(source)
    roles: dict[int, set[tuple[str, str]]] = {}

    def walk(item, alpha):
        if isinstance(item, dict):
            for key, value in item.items():
                if key in SLOTS and isinstance(value, dict) and isinstance(value.get("index"), int):
                    index = value["index"]
                    if 0 <= index < len(sources) and sources[index] is not None:
                        roles.setdefault(sources[index], set()).add((SLOTS[key], alpha))
                else:
                    walk(value, alpha)
        elif isinstance(item, list):
            for value in item:
                walk(value, alpha)

    for material in document.get("materials", []):
        walk(material, material.get("alphaMode", "OPAQUE"))
    return roles


def role_names(roles: set[tuple[str, str]]) -> list[str]:
    """The roles an index entry records, as the client (vram_textures.gd
    image_roles) names them: a base colour sampled by a MASK or BLEND
    material is base_cutout."""
    return sorted({"base_cutout" if role == "base" and alpha in ("MASK", "BLEND") else role
                   for role, alpha in roles})


def inventory(maps_roots: list[Path]) -> dict[str, dict]:
    """sha -> {path, roles: {(role, alphaMode)}, maps: set}"""
    found: dict[str, dict] = {}
    manifests = 0
    for root in maps_roots:
        for manifest_path in sorted(root.rglob("world.json")):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError):
                continue
            resources = manifest.get("externalResources") or {}
            if not isinstance(resources, dict) or not resources:
                continue
            # A territory root lists its chunks' resources, but its own GLB is
            # a review file the client never loads; the chunks carry the roles.
            if "streamingChunks" in manifest:
                for uri, sha in resources.items():
                    path = (manifest_path.parent / str(manifest.get("asset", {}).get("glb", "world.glb"))).parent / uri
                    found.setdefault(sha, {"path": path.resolve(), "roles": set(), "maps": set()})
                continue
            glb = manifest_path.parent / str(manifest.get("asset", {}).get("glb", "world.glb"))
            try:
                document = glb_json(glb)
            except (OSError, ValueError):
                continue
            manifests += 1
            roles = image_roles(document)
            by_uri = {str(image.get("uri")): index for index, image in enumerate(document.get("images", []))
                      if image.get("uri")}
            for uri, sha in resources.items():
                if not isinstance(sha, str) or len(sha) != 64:
                    continue
                record = found.setdefault(sha, {"path": (glb.parent / uri).resolve(), "roles": set(), "maps": set()})
                index = by_uri.get(uri)
                if index is not None:
                    record["roles"] |= roles.get(index, set())
                    record["maps"].add(str(manifest_path.parent.relative_to(root)))
    log(f"inventory: {len(found)} content-addressed images from {manifests} map packages")
    return found


def alpha_used(path: Path) -> bool:
    from PIL import Image
    with Image.open(path) as image:
        if image.mode not in ("RGBA", "LA", "P", "PA") and "transparency" not in image.info:
            return False
        import numpy as np
        return bool((np.asarray(image.convert("RGBA"))[..., 3] < 255).any())


def recipe_for(record: dict) -> tuple[str | None, str]:
    roles = {role for role, _ in record["roles"]}
    if not roles:
        return None, "no_material_role"
    if roles == {"normal"}:
        return "normal", ""
    if roles <= {"orm", "occlusion"}:
        return "orm", ""
    if roles <= {"base", "emissive"}:
        cutout = any(role == "base" and alpha in ("MASK", "BLEND") for role, alpha in record["roles"])
        if cutout and alpha_used(record["path"]):
            return "base_alpha", ""
        return "base", ""
    return None, "role_conflict: " + "+".join(sorted(roles))


# --- Godot -----------------------------------------------------------------------

def find_godot(explicit: str | None) -> Path:
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    if os.environ.get("ELORIA_GODOT"):
        candidates.append(Path(os.environ["ELORIA_GODOT"]))
    # The checkout's own copy, else the main checkout's beside (or above) this
    # worktree: the binary is untracked and lives in eloria-client only.
    candidates.append(CLIENT / GODOT_EXE)
    candidates += [parent / "eloria-client" / "godot-client" / GODOT_EXE for parent in REPO.parents]
    on_path = shutil.which("godot")
    if on_path:
        candidates.append(Path(on_path))
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise BuildError("Godot 4.7.2 editor binary not found; pass --godot or set ELORIA_GODOT")


def godot_version(godot: Path) -> str:
    out = subprocess.run([str(godot), "--headless", "--version"], capture_output=True, text=True,
                         timeout=120).stdout.strip().splitlines()
    version = out[-1].strip() if out else ""
    if not version.startswith("4."):
        raise BuildError(f"cannot read the Godot version from {godot}: {out!r}")
    return version


def encoder_project(cache: Path) -> Path:
    project = cache / "_encoder_project"
    project.mkdir(parents=True, exist_ok=True)
    (project / "project.godot").write_text(
        'config_version=5\n\n[application]\n\nconfig/name="eloria_vram_encode"\n\n'
        "[compression]\n\nformats/zstd/compression_level=19\n", encoding="utf-8", newline="\n")
    return project


def run_encoders(godot: Path, cache: Path, jobs: list[dict], procs: int) -> dict[str, dict]:
    if not jobs:
        return {}
    project = encoder_project(cache)
    work = cache / "_work"
    work.mkdir(parents=True, exist_ok=True)
    # Largest first, dealt round robin, so the processes finish together.
    jobs = sorted(jobs, key=lambda job: -os.path.getsize(job["src"]))
    batches = [jobs[index::procs] for index in range(procs)]
    env = dict(os.environ, APPDATA=str(cache / "_appdata"), LOCALAPPDATA=str(cache / "_appdata"),
               XDG_DATA_HOME=str(cache / "_appdata"), XDG_CONFIG_HOME=str(cache / "_appdata"))
    running = []
    for index, batch in enumerate(batches):
        if not batch:
            continue
        jobs_file = work / f"jobs{index}.json"
        jobs_file.write_text(json.dumps(batch), encoding="utf-8")
        log_file = open(work / f"encode{index}.log", "w", encoding="utf-8", errors="replace")
        process = subprocess.Popen([str(godot), "--headless", "--path", str(project), "--script", str(ENCODER)],
                                   stdout=log_file, stderr=subprocess.STDOUT,
                                   env=dict(env, VRAM_JOBS=str(jobs_file)))
        running.append((process, log_file, work / f"encode{index}.log"))
    results: dict[str, dict] = {}
    for process, log_file, log_path in running:
        process.wait(timeout=3600)
        log_file.close()
        for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("VRAM_RESULT "):
                result = json.loads(line[len("VRAM_RESULT "):])
                results[result["sha"]] = result
        if process.returncode != 0:
            raise BuildError(f"the encoder exited {process.returncode}; log: {log_path}")
    missing = [job["sha"] for job in jobs if job["sha"] not in results]
    if missing:
        raise BuildError(f"the encoder gave no result for {len(missing)} images, e.g. {missing[:3]}")
    return results


# --- quality ------------------------------------------------------------------------

def _box_mips(array, levels):
    import numpy as np
    out = [array.astype(np.float64)]
    for _ in range(levels):
        a = out[-1]
        h, w = a.shape[0] // 2 * 2, a.shape[1] // 2 * 2
        a = a[:h, :w]
        out.append(np.floor((a[0::2, 0::2] + a[1::2, 0::2] + a[0::2, 1::2] + a[1::2, 1::2] + 2) / 4))
    return out


def _dds_level(dds: bytes, fmt: str, width: int, height: int, level: int):
    """One mip level of a DDS, decoded with Pillow's BCn decoder, as float RGBA."""
    import numpy as np
    from PIL import Image
    offset = 128 + (20 if dds[84:88] == b"DX10" else 0)
    block = DDS_BLOCK_BYTES[fmt]
    for _ in range(level):
        offset += max(1, (width + 3) // 4) * max(1, (height + 3) // 4) * block
        width, height = max(1, width // 2), max(1, height // 2)
    size = max(1, (width + 3) // 4) * max(1, (height + 3) // 4) * block
    mode, n = PILLOW_BCN[fmt]
    image = Image.frombytes(mode, (width, height), dds[offset:offset + size], "bcn", n)
    return np.asarray(image.convert("RGBA")).astype(np.float64)


def _psnr(a, b) -> float:
    import numpy as np
    mse = float(np.mean((a - b) ** 2))
    return 99.0 if mse == 0 else 10 * np.log10(255.0 ** 2 / mse)


def measure(task: tuple) -> dict:
    """Quality of one encode against the source (Pillow decode + box mips)."""
    import numpy as np
    from PIL import Image
    source, dds_path, recipe, fmt, width, height = task
    dds = Path(dds_path).read_bytes()
    with Image.open(source) as image:
        reference = np.asarray(image.convert("RGBA")).astype(np.float64)
    decoded = _dds_level(dds, fmt, width, height, 0)
    metrics: dict = {}
    if recipe in ("base", "base_alpha"):
        metrics["psnr"] = round(_psnr(reference[..., :3], decoded[..., :3]), 2)
        bias = (decoded[..., :3] - reference[..., :3]).mean(axis=(0, 1))
        metrics["bias"] = [round(float(v), 3) for v in bias]
        if recipe == "base_alpha":
            metrics["alpha_flip_mip0"] = round(float(((reference[..., 3] >= 127.5) != (decoded[..., 3] >= 127.5)).mean()), 5)
            reference2 = _box_mips(reference[..., 3], 2)[2]
            decoded2 = _dds_level(dds, fmt, width, height, 2)[..., 3]
            metrics["alpha_flip_mip2"] = round(float(((reference2 >= 127.5) != (decoded2 >= 127.5)).mean()), 5)
    elif recipe == "normal":
        def unit(array):
            xy = array[..., :2] / 255.0 * 2 - 1
            z = np.sqrt(np.clip(1 - (xy ** 2).sum(-1), 0, 1))
            vector = np.dstack([xy, z])
            return vector / np.maximum(np.linalg.norm(vector, axis=-1, keepdims=True), 1e-6)
        angle = np.degrees(np.arccos(np.clip((unit(reference) * unit(decoded)).sum(-1), -1, 1)))
        metrics["mean_deg"] = round(float(angle.mean()), 3)
        metrics["p99_deg"] = round(float(np.percentile(angle, 99)), 3)
    elif recipe in ("orm", "orm_bc7"):
        metrics["psnr_rgb"] = [round(_psnr(reference[..., c], decoded[..., c]), 2) for c in range(3)]
    return metrics


def verdict(recipe: str, metrics: dict, floors: dict) -> str:
    if recipe in ("base", "base_alpha") and metrics["psnr"] < floors["base_psnr"]:
        return f"quality: psnr {metrics['psnr']} < {floors['base_psnr']}"
    if recipe == "base_alpha":
        if metrics["alpha_flip_mip0"] > floors["alpha_flip_mip0"]:
            return f"quality: alpha flips {metrics['alpha_flip_mip0']} > {floors['alpha_flip_mip0']} at mip 0"
        if metrics["alpha_flip_mip2"] > floors["alpha_flip_mip2"]:
            return f"quality: alpha flips {metrics['alpha_flip_mip2']} > {floors['alpha_flip_mip2']} at mip 2"
    if recipe == "normal" and (metrics["mean_deg"] > floors["normal_mean_deg"]
                               or metrics["p99_deg"] > floors["normal_p99_deg"]):
        return f"quality: normal error {metrics['mean_deg']} / {metrics['p99_deg']} deg"
    if recipe in ("orm", "orm_bc7") and min(metrics["psnr_rgb"]) < floors["orm_psnr"]:
        return f"quality: channel psnr {min(metrics['psnr_rgb'])} < {floors['orm_psnr']}"
    return ""


# --- the build ------------------------------------------------------------------------

def ensure_ignored(path: Path) -> None:
    """The encode cache must never become tracked content."""
    path.mkdir(parents=True, exist_ok=True)
    probe = subprocess.run(["git", "-C", str(path), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if probe.returncode != 0:
        return  # not inside a git worktree
    ignored = subprocess.run(["git", "-C", str(path), "check-ignore", "-q", str(path / "probe.evt")])
    if ignored.returncode != 0:
        raise BuildError(f"the encode cache {path} is inside a git worktree and not ignored; "
                         "pass --cache outside it or add it to .gitignore")


def cache_key(sha: str, recipe: str, version: str) -> str:
    return f"{sha}.{recipe}.r{RECIPE_VERSION}.{re.sub(r'[^A-Za-z0-9.]+', '_', version)}"


def build(maps_roots: list[Path], out_root: Path | None, cache: Path, godot: Path, procs: int,
          prune: bool = True, floors: dict | None = None) -> dict:
    floors = dict(FLOORS, **(floors or {}))
    started = time.time()
    ensure_ignored(cache)
    version = godot_version(godot)
    found = inventory(maps_roots)
    # Group by source directory: each gets its own vram/ folder.
    plans: dict[Path, dict] = {}
    for sha, record in sorted(found.items()):
        source_dir = record["path"].parent
        if not record["path"].is_file():
            continue
        if hashlib.sha256(record["path"].read_bytes()).hexdigest() != sha:
            raise BuildError(f"{record['path']} does not hash to its manifest sha {sha}")
        recipe, reason = recipe_for(record)
        plan = plans.setdefault(source_dir, {"images": {}, "excluded": {}})
        if recipe is None:
            plan["excluded"][sha] = reason
        else:
            plan["images"][sha] = {"recipe": recipe, "path": record["path"], "roles": role_names(record["roles"])}

    used_keys: set[str] = set()
    counts = {"encoded": 0, "cached": 0, "encodeSeconds": 0.0}

    def ensure(items: list[dict]) -> None:
        """Encodes and measures every item whose cache entry is missing."""
        jobs = []
        for item in items:
            key = cache_key(item["sha"], item["recipe"], version)
            item["key"] = key
            used_keys.add(key)
            if not ((cache / f"{key}.json").is_file() and (cache / f"{key}.evt").is_file()):
                jobs.append({"sha": item["sha"], "src": str(item["path"]), "recipe": item["recipe"],
                             "evt": str(cache / f"{key}.evt"), "dds": str(cache / "_work" / f"{key}.dds"),
                             "key": key})
        counts["cached"] += len(items) - len(jobs)
        counts["encoded"] += len(jobs)
        log(f"{len(items)} sidecars wanted: {len(items) - len(jobs)} cached, {len(jobs)} to encode")
        began = time.time()
        results = run_encoders(godot, cache, jobs, max(1, min(procs, len(jobs))))
        counts["encodeSeconds"] += time.time() - began
        tasks = []
        for job in jobs:
            result = results[job["sha"]]
            if "error" in result:
                meta = {"error": result["error"], "width": result.get("width"), "height": result.get("height")}
                (cache / f"{job['key']}.json").write_text(json.dumps(meta), encoding="utf-8")
                Path(job["evt"]).touch()
                continue
            tasks.append((job, result))
        if not tasks:
            return
        with futures.ProcessPoolExecutor(max_workers=max(1, min(os.cpu_count() or 4, 16))) as pool:
            quality = list(pool.map(measure, [(job["src"], job["dds"], job["recipe"], result["format"],
                                               result["width"], result["height"]) for job, result in tasks],
                                    chunksize=4))
        for (job, result), metrics in zip(tasks, quality):
            meta = {key: result[key] for key in ("format", "width", "height", "mipmaps", "gpuBytes",
                                                 "rawBytes", "fileBytes", "sha256", "encodeMs")}
            meta["quality"] = metrics
            (cache / f"{job['key']}.json").write_text(json.dumps(meta), encoding="utf-8")
            Path(job["dds"]).unlink(missing_ok=True)

    def meta_of(item: dict) -> dict:
        return json.loads((cache / f"{item['key']}.json").read_text(encoding="utf-8"))

    primary = []
    for plan in plans.values():
        for sha, item in plan["images"].items():
            item["sha"] = sha
            primary.append(item)
    ensure(primary)
    # A recipe below its floor gets one second chance where a better format
    # exists for the role: an ORM map whose channels BC1 cannot keep apart is
    # tried as BC7 (2x BC1's size, still a quarter of RGBA8).
    retry = []
    for item in primary:
        meta = meta_of(item)
        if (item["recipe"] in SECOND_CHANCE and "error" not in meta
                and verdict(item["recipe"], meta["quality"], floors)):
            retry.append(dict(item, recipe=SECOND_CHANCE[item["recipe"]], first=item))
    if retry:
        ensure(retry)
        for item in retry:
            if "error" not in meta_of(item) and not verdict(item["recipe"], meta_of(item)["quality"], floors):
                plans[item["path"].parent]["images"][item["sha"]] = item

    summary = {"encoder": f"godot {version} editor: Image.compress_from_channels (BPTC cvtt, S3TC etcpak)",
               "encoded": counts["encoded"], "cached": counts["cached"],
               "encodeSeconds": round(counts["encodeSeconds"], 1), "directories": {}}
    base_psnr = []
    for source_dir, plan in sorted(plans.items()):
        target = (out_root / source_dir.relative_to(common_root(maps_roots, source_dir)) / SIDECAR_DIR
                  if out_root else source_dir / SIDECAR_DIR)
        target.mkdir(parents=True, exist_ok=True)
        index = {"schema": SCHEMA, "recipeVersion": RECIPE_VERSION, "encoder": summary["encoder"],
                 "container": CONTAINER, "images": {}, "excluded": dict(sorted(plan["excluded"].items()))}
        report = {}
        for sha, item in sorted(plan["images"].items()):
            meta = json.loads((cache / f"{item['key']}.json").read_text(encoding="utf-8"))
            if "error" in meta:
                index["excluded"][sha] = meta["error"]
                continue
            reason = verdict(item["recipe"], meta["quality"], floors)
            report[sha] = {"recipe": item["recipe"], "width": meta["width"], **meta["quality"]}
            if reason:
                index["excluded"][sha] = reason
                continue
            if item["recipe"] in ("base", "base_alpha"):
                base_psnr.append(meta["quality"]["psnr"])
            name = f"{sha}.{item['recipe']}.evt"
            shutil.copyfile(cache / f"{item['key']}.evt", target / name)
            index["images"][sha] = {"file": name, "recipe": item["recipe"], "format": meta["format"],
                                    "width": meta["width"], "height": meta["height"],
                                    "mipmaps": meta["mipmaps"], "gpuBytes": meta["gpuBytes"],
                                    "rawBytes": meta["rawBytes"], "fileBytes": meta["fileBytes"],
                                    "sha256": meta["sha256"], "roles": item["roles"]}
        index["excluded"] = dict(sorted(index["excluded"].items()))
        wanted = {entry["file"] for entry in index["images"].values()}
        stale = [p for p in target.glob("*.evt") if p.name not in wanted]
        for path in stale:
            path.unlink()
        (target / "index.json").write_text(json.dumps(index, indent=1, sort_keys=False) + "\n",
                                           encoding="utf-8", newline="\n")
        (target / "report.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")
        reasons: dict[str, int] = {}
        for reason in index["excluded"].values():
            reasons[reason.split(":")[0]] = reasons.get(reason.split(":")[0], 0) + 1
        summary["directories"][str(target)] = {
            "sidecars": len(index["images"]), "excluded": reasons,
            "gpuMiB": round(sum(e["gpuBytes"] for e in index["images"].values()) / 1048576, 1),
            "fileMiB": round(sum(e["fileBytes"] for e in index["images"].values()) / 1048576, 1),
            "staleRemoved": len(stale)}
    if base_psnr:
        base_psnr.sort()
        median = base_psnr[len(base_psnr) // 2]
        summary["basePsnrMedian"] = median
        # A set-level gate: meaningless on a handful of test images.
        if len(base_psnr) >= 20 and median < floors["base_psnr_median"]:
            raise BuildError(f"median base-colour PSNR {median} is under {floors['base_psnr_median']} dB")
    if prune:
        removed = 0
        for path in cache.glob("*.json"):
            if path.stem not in used_keys:
                path.unlink()
                (cache / f"{path.stem}.evt").unlink(missing_ok=True)
                removed += 1
        summary["pruned"] = removed
    summary["seconds"] = round(time.time() - started, 1)
    return summary


def common_root(maps_roots: list[Path], source_dir: Path) -> Path:
    for root in maps_roots:
        try:
            source_dir.relative_to(root.resolve())
            return root.resolve()
        except ValueError:
            continue
    raise BuildError(f"{source_dir} is outside every --maps root")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--maps", type=Path, action="append",
                        help="map tree to scan for world.json (default <repo>/eloria-assets/maps); repeatable")
    parser.add_argument("--out-root", type=Path,
                        help="write <out-root>/<image dir relative to its --maps root>/vram instead of beside the images")
    parser.add_argument("--cache", type=Path, default=REPO / ".vram-encode-cache",
                        help="encode cache, a git-ignored directory (default <repo>/.vram-encode-cache)")
    parser.add_argument("--godot", help="Godot 4.7.2 editor binary (default: ELORIA_GODOT, the checkout's, PATH)")
    parser.add_argument("--procs", type=int, default=max(1, min(8, (os.cpu_count() or 2) // 2)))
    parser.add_argument("--no-prune", action="store_true", help="keep cache entries this run did not use")
    parser.add_argument("--floors", help="JSON object overriding quality floors (tests)")
    options = parser.parse_args()
    try:
        summary = build([p.resolve() for p in (options.maps or [REPO / "eloria-assets" / "maps"])],
                        options.out_root.resolve() if options.out_root else None,
                        options.cache.resolve(), find_godot(options.godot), options.procs,
                        prune=not options.no_prune, floors=json.loads(options.floors) if options.floors else None)
    except BuildError as error:
        log(f"FAILED: {error}")
        return 1
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
