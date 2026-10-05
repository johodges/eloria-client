#!/usr/bin/env python3
"""Build the client package that installs Eloria on another Windows or Linux machine.

Added 2026-09-16 for Eloria Client.

    python godot-client/tools/package_client.py                     # Windows, origin/develop
    python godot-client/tools/package_client.py --platform linux    # Linux
    python godot-client/tools/package_client.py --ref HEAD --installer

The package is built from a commit, never from a working tree. The main
checkout is shared with other sessions and always holds someone's unfinished
edits, so the script keeps its own detached worktree (dist/.build/client-src
beside the repositories), forces it to the commit, imports it and exports it.
Nothing it does touches the checkout it is run from.

What goes in, and why it is more than an export:

  app/Eloria.exe (Windows) or app/Eloria.x86_64 (Linux), app/Eloria.pck
      The Godot export. Scripts, scenes, UI art and data. Linux needs the
      official 4.7.2 export templates installed beside the Windows ones.
  app/assets, app/data, app/schemas
      Loose copies, and every actor file ships once (or not at all). Actor
      models, hair and equipment are opened with GLTFDocument from
      ProjectSettings.globalize_path("res://assets/..."). An exported build
      has no resource path, so that is a path relative to the folder the game
      starts in, which ResourceLoader never maps back into the pack:
      GlbSceneCache's imported-scene route is only taken in an editor
      checkout, and an imported scene in the PCK would never be read. The
      glTF files therefore ship loose only and are never imported (a folder
      with nothing for the PCK gets a .gdignore, which also keeps ~4 GB out of
      the import; elsewhere each glTF gets a "skip" import). Two kinds of
      actor file are read through ResourceLoader and ship in the PCK only:
      the face masks, which models.json names and replicated_actor_3d.gd
      load()s, and the textures the equipment glTFs name by relative URI.
      GLTFDocument tries ResourceLoader first for an external image, and a
      relative path resolves to res://, so the packager writes those
      textures' import settings (VRAM-compressed, mipmapped: what the editor
      gives a texture it sees used in 3D) and the game uploads the imported
      texture instead of decoding the JPEG with no mip chain. GLTFDocument
      then reads each such texture back with get_image(), a RenderingServer
      call: it stalls the GPU on the main thread and, from a worker, waits
      for the main thread, so an equipment glTF must never be parsed on a
      worker the main thread joins (GlbSceneCache, NativeAnimationImporter).
      Actor images that nothing names - no glTF URI, no catalog, no client
      source, no other text the package carries; the editor's extracted
      copies of embedded glTF images and the race and neck texture sources
      the race models were built from - ship nowhere.
  eloria-assets/maps, eloria-assets/concepts
      "res://../eloria-assets/..." resolves beside app/. Every map package (a
      folder holding world.json) ships without its references, captures,
      sources, reports and unused world-lod2.glb; any other file a shipped
      manifest or the map registry names is pulled in even if the filter
      dropped it.
  eloria-assets/maps/.../shared-assets/vram
      VRAM-compressed (BC7/BC5/BC1) copies of the shared map images, made at
      package time by tools/build_vram_textures.py (they are not tracked), so
      the client uploads them as they are instead of decoding each image to
      RGBA8. Checked against their index; --no-vram-textures leaves them out.

Only files tracked at the commit are shipped. Before zipping, the package is
checked - every registry manifest, the files each manifest names, and every
external texture a GLB references must be present - and the exported game is
started headless once with a throwaway user directory, failing on any script
error. The Linux build is started under WSL (Ubuntu-24.04) when it is present.

Windows ships as a zip with .bat launchers. Linux ships as a .tar.gz with .sh
launchers: a zip made on Windows cannot mark the game executable.

--installer also compiles an Inno Setup installer (per-user, no admin, Start
menu shortcut, uninstaller) when ISCC.exe is available. Inno Setup is not part
of the repository: https://jrsoftware.org/isdl.php
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import posixpath
import re
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

CLIENT = Path(__file__).resolve().parents[1]
REPO = CLIENT.parent
PROJECT = REPO.parent
DIST = PROJECT / "dist"
GODOT_EXE = "Godot_v4.7.2-stable_win64_console.exe"
MARKER = ".eloria-package"
ASSET_REF = re.compile(r"res://\.\./(eloria-assets/[^\"'\s]+)")

# The installer's identity. Keep it fixed: Windows matches upgrades and the
# uninstaller entry on it.
INSTALLER_APP_ID = "{6B1E9F4C-3A52-4D8E-9C71-5E0B2F8A4D17}"

# Folders and files inside a map package that the client never reads.
MAP_EXCLUDED_DIRS = {"references", "captures", "godot-captures", "source",
                     "sources", "qa", "reports", "review", "renders"}
MAP_EXCLUDED_SUFFIXES = {".py", ".md", ".gd", ".c", ".txt", ".gitignore"}
# Reduced-detail map packages (world-lod2.glb, 335 MB across eleven maps) and
# their manifests and statistics. Manifests list them under lodGroups and the
# registry names Sunmane's under "lod2", but no client code loads either.
MAP_LOD_PACKAGE = re.compile(r"^(world-lod\d+|build-statistics-lod\d+)\b")
# Manifest keys that describe provenance, or files the client never opens.
MANIFEST_SKIPPED_KEYS = {"sources", "provenance", "knownLimitations", "lodGroups"}
FILE_LIKE = re.compile(r"^[^:*?\"<>|\s]+\.(glb|gltf|bin|json|webp|png|jpg|jpeg|gz|escg|ogg|wav)$", re.I)
# "Can't open file" is GLTFDocument's error when a loose actor GLB is missing.
# The last four are WARNING-level: an actor part that fell back rather than
# failed. A torso cover profile whose fingerprint does not match drops a whole
# reviewed surface (the packaged Orun male did, for every class loadout), and
# a scene that cannot be packed or a hairstyle that cannot be bound simply
# goes missing. None of them is a load error, so the old list let them pass.
SMOKE_FAILURES = ("SCRIPT ERROR", "Parse Error", "Failed to load script",
                  "No loader found", "Cannot open file", "Can't open file",
                  "Failed loading resource",
                  "Ignoring torso cover profile", "glb cache: pack failed",
                  "Native hairstyle failed to load",
                  "Fitted hairstyle has an incompatible skeleton")

ACTOR_ROOT = "godot-client/assets/actors/native"
ACTOR_CATALOGS = ("godot-client/data/actors/models.json", "godot-client/data/actors/equipment.json")
GLTF_SUFFIXES = (".glb", ".gltf")
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")
# Files the export's include filter packs whether or not they are imported.
PLAIN_EXPORT_SUFFIXES = (".json", ".bin")
# Client files whose string literals may name an actor file the game opens:
# the scripts, scenes, resources, shaders and settings the export packs from
# anywhere in the project (src, addons, world_authoring, assets), and the
# native extension's sources. The export's exclude filter keeps docs, tests
# and tools out of a package, so nothing a package runs is written there.
SOURCE_SUFFIXES = (".gd", ".tscn", ".tres", ".gdshader", ".gdshaderinc", ".godot", ".cfg",
                   ".gdextension", ".cpp", ".h")
UNSHIPPED_CLIENT_DIRS = ("godot-client/docs/", "godot-client/tests/", "godot-client/tools/",
                         "godot-client/test-artifacts/")
# Data the game reads as text beside its JSON (the localisation table).
PLAIN_TEXT_SUFFIXES = (".csv", ".txt")
# A string literal in either quote style (GDScript takes both).
SOURCE_LITERAL = re.compile(r"""(["'])((?:(?!\1)[^\\\n])*)\1""")
# Where a string names a path under the actor tree: "res://assets/actors/...",
# "assets/actors", ".../godot-client/assets/actors/..." - not eloria-assets/actors.
ACTOR_PATH_IN_TEXT = re.compile(r"(?<![\w.-])assets/actors(?=/|$)", re.I)
# A path literal compared against another path reaches nothing.
COMPARED_BEFORE = re.compile(r"(begins_with|ends_with|contains|find|rfind|==|!=)\(?\s*$")
# A literal joined to more text builds a path from its start.
JOINED_AFTER = re.compile(r"\s*(\+|%|\.path_join|\.plus_file|\.format)")
# A literal inside a "/".join([...]) list is one piece of a built path.
JOIN_LIST_BEFORE = re.compile(r"\.join\(\s*\[[^\]\)]*$")

# Actor folders whose glTF files' URI-named textures are imported into the
# PCK (owner call, 2026-10-05: "keep equipment textures imported", +95 MB).
# GLTFDocument asks ResourceLoader for an external image before it reads the
# file, and the relative path an export globalizes to resolves to res://, so
# the 384 equipment textures load VRAM-compressed with mip chains, as the
# stage-1 package (every actor imported) loaded them, rather than as raw JPEG
# decodes without mips. Other folders' URI images (the 12 the shared
# Superhero glTFs name; no catalog names those glTFs) stay loose, as before.
IMPORTED_URI_TEXTURE_FOLDERS = ("equipment",)
# The import settings those textures get: what the editor's 3D detection
# writes for a texture a material uses (VRAM Compressed - S3TC/BPTC in the
# preset - plus mipmaps). Godot reads [params] from an existing .import, and
# imports again only when they change, so a rebuild keeps its imports.
URI_TEXTURE_IMPORT_PARAMS = (
    ("compress/mode", "2"), ("compress/high_quality", "false"), ("compress/lossy_quality", "0.7"),
    ("compress/uastc_level", "0"), ("compress/rdo_quality_loss", "0.0"),
    ("compress/hdr_compression", "1"), ("compress/normal_map", "0"), ("compress/channel_pack", "0"),
    ("mipmaps/generate", "true"), ("mipmaps/limit", "-1"), ("roughness/mode", "0"),
    ("roughness/src_normal", '""'), ("process/channel_remap/red", "0"),
    ("process/channel_remap/green", "1"), ("process/channel_remap/blue", "2"),
    ("process/channel_remap/alpha", "3"), ("process/fix_alpha_border", "true"),
    ("process/premult_alpha", "false"), ("process/normal_map_invert_y", "false"),
    ("process/hdr_as_srgb", "false"), ("process/hdr_clamp_exposure", "false"),
    ("process/size_limit", "0"), ("detect_3d/compress_to", "0"),
)
SKIP_IMPORT = '[remap]\n\nimporter="skip"\n'
# Actor folders whose unnamed images ship nowhere (owner call, 2026-10-05:
# "verify, then drop", ~116 MB). In these folders an image that no actor glTF
# names by URI, no catalog names and no client source names is never read by
# a package: the equipment and creature PNGs are the editor's extracted copies
# of images their GLBs embed (a package parses the GLB and uses the embedded
# bytes), race_textures holds the sources the Luminous race models were built
# from, and neck_textures the bakes no model names any more (models.json has
# no faceAppearance.neckTexture). A catalog or source reference keeps a file;
# a client literal that builds paths under one of these folders keeps all of
# its images. Proven unused statically and on a package without them, in
# work-output/integration-2026-10-04/stage2b.
UNREFERENCED_IMAGE_FOLDERS = ("creatures", "equipment", "neck_textures", "race_textures")

# The export preset is not tracked, so the build writes its own. The pack
# leaves out dev material, including the map editor's review notes
# (<region>.editor-notes.json beside each region scene): editor-only, never read
# by the game. Actor files are kept out of the import, and so out of the pack,
# by a .gdignore per folder or a "skip" import per file (see actor_shipping),
# not by a filter, so the face masks and equipment textures still import.
EXPORT_PRESETS = """[preset.0]

name="Windows Desktop"
platform="Windows Desktop"
runnable=true
advanced_options=false
dedicated_server=false
custom_features=""
export_filter="all_resources"
include_filter="*.json,*.bin"
exclude_filter="Godot_v*.exe,docs/*,tests/*,tools/*,test-artifacts/*,*.md,*.editor-notes.json"
export_path=""
patches=PackedStringArray()
encryption_include_filters=""
encryption_exclude_filters=""
seed=0
encrypt_pck=false
encrypt_directory=false
script_export_mode=2

[preset.0.options]

custom_template/debug=""
custom_template/release=""
debug/export_console_wrapper=2
binary_format/embed_pck=false
texture_format/s3tc_bptc=true
texture_format/etc2_astc=false
binary_format/architecture="x86_64"
application/modify_resources=true
application/icon=""
application/console_wrapper_icon=""
application/icon_interpolation=4
application/file_version=""
application/product_version=""
application/company_name="Eloria"
application/product_name="Eloria"
application/file_description="Eloria Client"
application/copyright=""
application/trademarks=""
application/export_angle=0
application/export_d3d12=0
application/d3d12_agility_sdk_multiarch=true
ssh_remote_deploy/enabled=false

[preset.1]

name="Linux"
platform="Linux"
runnable=false
advanced_options=false
dedicated_server=false
custom_features=""
export_filter="all_resources"
include_filter="*.json,*.bin"
exclude_filter="Godot_v*.exe,docs/*,tests/*,tools/*,test-artifacts/*,*.md,*.editor-notes.json"
export_path=""
patches=PackedStringArray()
encryption_include_filters=""
encryption_exclude_filters=""
seed=0
encrypt_pck=false
encrypt_directory=false
script_export_mode=2

[preset.1.options]

custom_template/debug=""
custom_template/release=""
debug/export_console_wrapper=0
binary_format/embed_pck=false
texture_format/s3tc_bptc=true
texture_format/etc2_astc=false
binary_format/architecture="x86_64"
ssh_remote_deploy/enabled=false
"""

PLATFORMS = {
    "windows": {"preset": "Windows Desktop", "binary": "Eloria.exe", "folder": "Eloria-Windows"},
    "linux": {"preset": "Linux", "binary": "Eloria.x86_64", "folder": "Eloria-Linux"},
}
WSL_DISTRO = "Ubuntu-24.04"


class PackageError(RuntimeError):
    pass


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def git(*args: str, cwd: Path = REPO, capture: bool = True) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, text=True,
                            capture_output=capture, encoding="utf-8")
    if result.returncode != 0:
        raise PackageError(f"git {' '.join(args)} failed:\n{result.stderr}")
    return result.stdout if capture else ""


def tracked(tree: Path, *pathspecs: str) -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z", "--", *pathspecs], cwd=tree,
                         capture_output=True, check=True).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


def _catalog_strings(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from _catalog_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _catalog_strings(child)
    elif isinstance(value, str):
        yield value


def gltf_image_uris(path: Path) -> list[str]:
    """The relative image URIs a .glb/.gltf names (decoded; data: URIs left out).

    Reads only the JSON chunk. A file that is not glTF names nothing.
    """
    try:
        if path.suffix.lower() == ".glb":
            with open(path, "rb") as handle:
                header = handle.read(20)
                if len(header) < 20 or header[:4] != b"glTF":
                    return []
                length = struct.unpack("<I", header[12:16])[0]
                document = json.loads(handle.read(length).rstrip(b"\0 ").decode("utf-8"))
        else:
            document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, struct.error):
        return []
    uris = []
    for image in document.get("images", []) if isinstance(document, dict) else []:
        uri = image.get("uri") if isinstance(image, dict) else None
        if isinstance(uri, str) and uri and not uri.startswith("data:"):
            uris.append(unquote(uri))
    return uris


def _resolve(base: str, relative: str) -> str:
    return posixpath.normpath(posixpath.join(posixpath.dirname(base), relative.replace("\\", "/")))


def shipped_client_files(build_dir: Path, suffixes: tuple[str, ...]) -> list[str]:
    """Tracked godot-client files with these suffixes that a package carries (not docs/tests/tools)."""
    return [p for p in tracked(build_dir, "godot-client")
            if p.lower().endswith(suffixes) and not p.startswith(UNSHIPPED_CLIENT_DIRS)
            and not p.lower().endswith(".md")]


def _actor_path(literal: str) -> str | None:
    """The repository path an actor path string names or starts, or None.

    Takes res://, repository, project and absolute forms ("res://assets/actors/
    native/x", "assets/actors", ".../godot-client/assets/actors/...").
    """
    text = literal.replace("\\", "/")
    match = ACTOR_PATH_IN_TEXT.search(text)
    return "godot-client/" + text[match.start():] if match else None


def _actor_prefix(build_dir: Path, path: str) -> str | None:
    """The start of the actor paths `path` builds at runtime, or None when it names one file.

    A format placeholder (%s, {0}) builds from the text before it; a path
    ending in "/", "_" or "-", or naming a directory (its last part has no
    suffix, or it is one in the tree), is joined to more at runtime.
    """
    placeholder = re.search(r"%|\{", path)
    if placeholder:
        return path[:placeholder.start()]
    if path.endswith(("/", "_", "-")) or not PurePosixPath(path).suffix or (build_dir / path).is_dir():
        return path
    return None


def source_actor_literals(build_dir: Path) -> tuple[set[str], set[str]]:
    """Actor paths the client source names: (files, prefixes) as repository paths.

    Every string literal, in either quote style, in every source file a
    package carries (SOURCE_SUFFIXES outside docs/tests/tools: src, addons,
    world_authoring, the native extension, project.godot). A literal naming an
    actor file is a file the game may open. A literal that is only the start
    of actor paths builds paths at runtime, so it can reach any file under it:
    one that names a directory ("res://assets/actors/native", "...race_textures"
    kept in a const and path_join()ed later), ends in "/", "_" or "-", holds a
    format placeholder, is joined to more text (+, %, path_join, format) or
    sits in a "/".join([...]) list. One compared against a path (begins_with
    and the like) reaches nothing. Paths built with no literal naming
    assets/actors at all are beyond this: shipped_text_names() and the
    packaged-route checks are the net under it.
    """
    files: set[str] = set()
    prefixes: set[str] = set()
    for relative in shipped_client_files(build_dir, SOURCE_SUFFIXES):
        text = (build_dir / relative).read_text(encoding="utf-8", errors="replace")
        if not ACTOR_PATH_IN_TEXT.search(text):
            continue
        for match in SOURCE_LITERAL.finditer(text):
            path = _actor_path(match.group(2))
            if path is None:
                continue
            before = text[max(0, match.start() - 200):match.start()]
            after = text[match.end():match.end() + 16]
            if COMPARED_BEFORE.search(before[-16:]):
                continue
            prefix = _actor_prefix(build_dir, path)
            if prefix is not None:
                prefixes.add(prefix)
            elif JOINED_AFTER.match(after) or JOIN_LIST_BEFORE.search(before):
                prefixes.add(path)
            else:
                files.add(path)
    return files, prefixes


def _json_strings(value):
    """Every key and string value in a JSON document."""
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _json_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _json_strings(child)
    elif isinstance(value, str):
        yield value


def shipped_text_names(build_dir: Path, candidates: set[str]) -> dict[str, set[str]]:
    """Which of `candidates` (actor images about to be dropped) shipped text names, and where.

    The drop is decided from the actor catalogs, the client source's actor
    path literals and the actor glTFs' URIs. This is the wider net under that
    decision - the scan the stage-2b static proof made - so that an image some
    other shipped text names is kept rather than silently left out:

      * every JSON a package carries, keys and values: godot-client outside
        docs/tests/tools (data, schemas, assets, world_authoring, the actor
        manifests) and the eloria-assets files that ship (shipped_eloria_assets:
        provenance, QA and review records stay out of a package, and their
        paths name nothing the game reads), plus the plain-text data (the
        localisation CSV);
      * every string literal, either quote style, in the source files a package
        carries (see source_actor_literals);
      * the image URIs of every other glTF a package carries.

    A string names a candidate when it is the image's path or a tail of it -
    its bare file name, "race_textures/x/body.png", a res://, repository or
    absolute path - or when, holding assets/actors, it is a directory, a path
    prefix or a format string the image lies under (JSON and plain text only;
    source prefixes are source_actor_literals', which knows a comparison from
    a built path). A bare stem ("orun_male") is not a name: stems are model
    keys and face-mask names, and a path built from a stem needs a folder,
    which these rules look for. Returns {candidate: {"<file>: <string>", ...}}.
    """
    if not candidates:
        return {}
    tails: dict[str, set[str]] = {}
    for candidate in candidates:
        parts = candidate.lower().split("/")
        for index in range(len(parts)):
            tails.setdefault("/".join(parts[index:]), set()).add(candidate)
    lowered = sorted((c.lower(), c) for c in candidates)
    named: dict[str, set[str]] = {}

    def note(hits, where: str, token: str) -> None:
        for hit in hits:
            named.setdefault(hit, set()).add(f"{where}: {token[:160]}")

    def visit(token: str, where: str, prefixes: bool) -> None:
        original = unquote(token).replace("\\", "/").strip()
        if not original or len(original) > 1024:
            return
        if original[:6].lower() == "res://":
            original = original[6:]
        original = original.removeprefix("./")
        hits = set(tails.get(original.lower(), ()))
        path = _actor_path(original)
        if path is not None:
            hits |= tails.get(path.lower(), set())
            prefix = _actor_prefix(build_dir, path) if prefixes else None
            if prefix is not None:
                prefix = prefix.lower()
                hits |= {c for low, c in lowered if low.startswith(prefix)}
        if hits:
            note(hits, where, token)

    map_files = sorted(shipped_eloria_assets(build_dir)[0])
    json_files = shipped_client_files(build_dir, (".json",)) + [
        p for p in map_files if p.lower().endswith(".json")]
    for relative in json_files:
        try:
            document = json.loads((build_dir / relative).read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            text = (build_dir / relative).read_text(encoding="utf-8", errors="replace")
            for match in SOURCE_LITERAL.finditer(text):
                visit(match.group(2), relative, True)
            continue
        for value in _json_strings(document):
            visit(value, relative, True)
    for relative in shipped_client_files(build_dir, PLAIN_TEXT_SUFFIXES):
        text = (build_dir / relative).read_text(encoding="utf-8", errors="replace")
        for token in re.split(r"[\s\"',;=()\[\]{}<>|]+", text):
            visit(token, relative, True)
    for relative in shipped_client_files(build_dir, SOURCE_SUFFIXES):
        text = (build_dir / relative).read_text(encoding="utf-8", errors="replace")
        for match in SOURCE_LITERAL.finditer(text):
            visit(match.group(2), relative, False)
    gltf_files = [p for p in shipped_client_files(build_dir, GLTF_SUFFIXES) + map_files
                  if p.lower().endswith(GLTF_SUFFIXES) and not p.startswith(ACTOR_ROOT + "/")]
    for relative in gltf_files:
        for uri in gltf_image_uris(build_dir / relative):
            target = _resolve(relative, uri)
            if target in candidates:
                note({target}, relative, uri)
            elif ACTOR_PATH_IN_TEXT.search(uri):
                visit(uri, relative, False)
    return named


def actor_shipping(build_dir: Path) -> dict:
    """Decide, per actor file, whether it ships in the PCK, loose or nowhere - never twice.

    The client reaches actor files three ways. glTF files (models, hair,
    equipment, animation libraries, held props) go through GlbSceneCache and
    NativeAnimationImporter with ProjectSettings.globalize_path(), which in an
    exported build is relative to the working folder: they are read loose,
    and a PCK copy would never be read. An actor file the catalogs or the
    client source name by res:// path (today the face masks) is load()ed
    through ResourceLoader and must be in the PCK. And the images a glTF names
    by relative URI are asked of ResourceLoader first, at that relative path,
    which resolves to res://: in IMPORTED_URI_TEXTURE_FOLDERS they are
    imported into the PCK; elsewhere they are read loose beside their glTF.
    An image in UNREFERENCED_IMAGE_FOLDERS that none of these names, and no
    runtime-built source path can reach, ships nowhere - unless any other text
    a package carries names it (shipped_text_names), which keeps it loose,
    as every actor image shipped before the drop.

    A folder under assets/actors/native with nothing for the PCK gets a
    .gdignore (neither imported nor exported); in a folder that has, each
    other importable file gets a "skip" import, and its .json/.bin files are
    packed by the export's include filter, so they ship in the PCK. Returns
    {"pck", "loose", "dropped"} (tracked files), "uri_textures" (the imported
    URI textures, a subset of "pck"), "kept" ({image: where it is named} for
    the images the wider scan kept loose) and {"pck_folders", "loose_folders"}.
    """
    actor_files = tracked(build_dir, ACTOR_ROOT)
    folders: dict[str, list[str]] = {}
    for relative in actor_files:
        parts = PurePosixPath(relative).relative_to(ACTOR_ROOT).parts
        if len(parts) < 2:
            raise PackageError(f"{relative} sits outside an actor folder; it would ship nowhere")
        folders.setdefault(f"{ACTOR_ROOT}/{parts[0]}", []).append(relative)
    tracked_set = set(actor_files)
    loaded: set[str] = set()
    for catalog in ACTOR_CATALOGS:
        document = json.loads((build_dir / catalog).read_text(encoding="utf-8"))
        for value in _catalog_strings(document):
            if value.startswith("res://assets/actors/") and not value.lower().endswith(GLTF_SUFFIXES):
                loaded.add("godot-client/" + value[len("res://"):])
    missing = sorted(loaded - tracked_set)
    if missing:
        raise PackageError("actor resources the catalogs load are not in the commit:\n  "
                           + "\n  ".join(missing[:40]))
    source_files, source_prefixes = source_actor_literals(build_dir)
    loaded |= {f for f in source_files & tracked_set if not f.lower().endswith(GLTF_SUFFIXES)}
    uri_named: dict[str, str] = {}
    for relative in actor_files:
        if relative.lower().endswith(GLTF_SUFFIXES):
            for uri in gltf_image_uris(build_dir / relative):
                target = _resolve(relative, uri)
                if target in tracked_set:
                    uri_named.setdefault(target, relative)

    def folder_name(relative: str) -> str:
        return PurePosixPath(relative).relative_to(ACTOR_ROOT).parts[0]

    uri_textures = {f for f in uri_named
                    if folder_name(f) in IMPORTED_URI_TEXTURE_FOLDERS and f not in loaded}
    reached = tuple(p for p in source_prefixes if p.startswith(ACTOR_ROOT + "/")
                    or (ACTOR_ROOT + "/").startswith(p))
    unnamed = {f for f in actor_files
               if f.lower().endswith(IMAGE_SUFFIXES) and folder_name(f) in UNREFERENCED_IMAGE_FOLDERS
               and f not in uri_named and f not in loaded and not f.startswith(reached)}
    # Any other shipped text that names one keeps it, loose, as before the drop.
    kept = shipped_text_names(build_dir, unnamed)
    dropped = unnamed - set(kept)
    pck_folders = {folder for folder, files in folders.items()
                   if (loaded | uri_textures).intersection(files)}
    for folder in sorted(pck_folders):
        # A .gltf reads its .bin buffers loose, but the include filter would
        # pack them (a .glb carries its own).
        gltf = [f for f in folders[folder] if f.lower().endswith(".gltf")]
        if gltf:
            raise PackageError(f"{folder} ships files in the PCK and holds {gltf[0]}, whose "
                               "buffers the export would pack instead of shipping beside it; "
                               "split the folder")
    pck = loaded | uri_textures | {f for folder in pck_folders for f in folders[folder]
                                   if f.lower().endswith(PLAIN_EXPORT_SUFFIXES)}
    loose_folders = set(folders) - pck_folders
    return {"pck": pck, "uri_textures": uri_textures, "dropped": dropped, "kept": kept,
            "loose": tracked_set - pck - dropped,
            "pck_folders": pck_folders, "loose_folders": loose_folders}


def find_godot(explicit: str | None) -> Path:
    candidates = [Path(explicit)] if explicit else [
        CLIENT / GODOT_EXE, PROJECT / "eloria-client" / "godot-client" / GODOT_EXE]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise PackageError("Godot not found; pass --godot <path to " + GODOT_EXE + ">")


def find_iscc(explicit: str | None) -> Path | None:
    candidates = [Path(explicit)] if explicit else [
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe"]
    found = shutil.which("iscc")
    if found and not explicit:
        candidates.insert(0, Path(found))
    return next((c for c in candidates if c.is_file()), None)


# --- build tree ------------------------------------------------------------

def prepare_build_tree(build_dir: Path, sha: str) -> Path:
    if not (build_dir / ".git").exists():
        log(f"creating build worktree {build_dir}")
        build_dir.parent.mkdir(parents=True, exist_ok=True)
        git("worktree", "add", "--detach", str(build_dir), sha)
    else:
        log(f"moving build worktree to {sha[:9]}")
        git("checkout", "--detach", "--force", sha, cwd=build_dir)
        # Untracked, unignored leftovers (a file deleted since the last build)
        # would otherwise be exported. Ignored files - .godot and the .import
        # sidecars - survive, which is what keeps a rebuild's import short.
        git("clean", "-ffd", "-q", cwd=build_dir)
    project = build_dir / "godot-client"
    (project / "export_presets.cfg").write_text(EXPORT_PRESETS, encoding="utf-8", newline="\n")
    # The loose-only actor folders are neither imported nor exported. git
    # clean preserves ignored files, so set every marker explicitly: an older
    # build's assets/actors/.gdignore would also hide the face masks.
    shipping = actor_shipping(build_dir)
    (project / "assets" / "actors" / ".gdignore").unlink(missing_ok=True)
    for folder in shipping["pck_folders"]:
        (build_dir / folder / ".gdignore").unlink(missing_ok=True)
    for folder in shipping["loose_folders"]:
        (build_dir / folder / ".gdignore").write_text("", encoding="utf-8")
    write_actor_import_settings(build_dir, shipping)
    for image, where in sorted(shipping["kept"].items()):
        log(f"kept loose, named outside the catalogs: {image} ({'; '.join(sorted(where)[:3])})")
    return project


def _import_settings(sidecar: Path) -> tuple[str, dict[str, str]]:
    """(importer, [params]) of a .import file, as raw text values."""
    importer = ""
    params: dict[str, str] = {}
    section = ""
    for line in sidecar.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
        elif "=" in line:
            key, _, value = line.partition("=")
            if section == "remap" and key == "importer":
                importer = value.strip('"')
            elif section == "params":
                params[key] = value
    return importer, params


def pck_folder_others(build_dir: Path, shipping: dict) -> list[str]:
    """Every file on disk in an actor folder the PCK draws on that must not be imported.

    Not only the tracked loose files: the build worktree keeps ignored files,
    and an earlier import's extracted images (equipment/*_0.jpg, gitignored)
    sit there too. Godot imports whatever it finds in a folder without a
    .gdignore, so each of them needs its "skip" as much as a tracked glTF
    does. A .json or .bin that is not a PCK file stops the build: the
    export's include filter would pack it whatever its import says.
    """
    others: list[str] = []
    for folder in sorted(shipping["pck_folders"]):
        for path in sorted((build_dir / folder).rglob("*")):
            relative = path.relative_to(build_dir).as_posix()
            if not path.is_file() or path.name == ".gdignore" or path.suffix in {".import", ".uid"}:
                continue
            if relative in shipping["pck"]:
                continue
            if relative.lower().endswith(PLAIN_EXPORT_SUFFIXES):
                raise PackageError(f"{relative} is not a PCK file, but the export would pack it "
                                   "from a folder the PCK draws on; remove it from the build worktree")
            others.append(relative)
    return others


def write_actor_import_settings(build_dir: Path, shipping: dict) -> dict:
    """Write the import settings of every file in an actor folder the PCK draws on.

    The URI textures get URI_TEXTURE_IMPORT_PARAMS and every other file there
    a "skip" import (glTF scenes would never be read from the PCK, and
    dropped images ship nowhere); a load()ed resource keeps the editor's
    defaults, so a "skip" left by an older build is removed. A .import that
    already says what is wanted is left alone - Godot rewrites it with the
    imported product's paths, and rewriting it here would import again.
    Returns counts of what was written.
    """
    counts = {"texture": 0, "skip": 0, "default": 0, "kept": 0}
    wanted = dict(URI_TEXTURE_IMPORT_PARAMS)
    for relative in sorted(shipping["uri_textures"]):
        sidecar = build_dir / (relative + ".import")
        if sidecar.is_file():
            importer, params = _import_settings(sidecar)
            if importer == "texture" and all(params.get(k) == v for k, v in wanted.items()):
                counts["kept"] += 1
                continue
        sidecar.write_text('[remap]\n\nimporter="texture"\ntype="CompressedTexture2D"\n\n[params]\n\n'
                           + "".join(f"{k}={v}\n" for k, v in URI_TEXTURE_IMPORT_PARAMS),
                           encoding="utf-8", newline="\n")
        counts["texture"] += 1
    for relative in pck_folder_others(build_dir, shipping):
        sidecar = build_dir / (relative + ".import")
        if sidecar.is_file() and _import_settings(sidecar)[0] == "skip":
            counts["kept"] += 1
            continue
        sidecar.write_text(SKIP_IMPORT, encoding="utf-8", newline="\n")
        counts["skip"] += 1
    for relative in sorted(shipping["pck"] - shipping["uri_textures"]):
        sidecar = build_dir / (relative + ".import")
        if sidecar.is_file() and _import_settings(sidecar)[0] == "skip":
            sidecar.unlink()
            counts["default"] += 1
    log(f"actor import settings: {counts['texture']} URI textures and {counts['skip']} skipped files "
        f"written, {counts['default']} skips removed, {counts['kept']} already right")
    return counts


def run_godot(godot: Path, args: list[str], log_file: Path, timeout: int,
              env: dict | None = None) -> str:
    with open(log_file, "w", encoding="utf-8", errors="replace") as handle:
        try:
            result = subprocess.run([str(godot), *args], stdout=handle, stderr=subprocess.STDOUT,
                                    timeout=timeout, env=env)
        except subprocess.TimeoutExpired:
            raise PackageError(f"Godot timed out after {timeout}s; log: {log_file}")
    text = log_file.read_text(encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise PackageError(f"Godot exited {result.returncode}; log: {log_file}\n{text[-2000:]}")
    return text


def import_project(godot: Path, project: Path, logs: Path) -> None:
    # --import can exit 0 long before the scan finishes; repeat until the
    # imported set stops growing.
    imported = project / ".godot" / "imported"
    previous = -1
    for attempt in range(1, 7):
        log(f"importing (pass {attempt})")
        run_godot(godot, ["--headless", "--path", str(project), "--import"],
                  logs / f"import-{attempt}.log", timeout=3600)
        count = sum(1 for _ in imported.iterdir()) if imported.is_dir() else 0
        log(f"  {count} imported files")
        if count == previous:
            return
        previous = count
    raise PackageError("import never settled after 6 passes; see import-*.log")


def _import_products(sidecar: Path) -> list[str]:
    text = sidecar.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"(?m)^dest_files=\[(.*)\]\s*$", text)
    return re.findall(r'"res://([^"]+)"', match.group(1)) if match else []


def check_actor_imports(project: Path) -> None:
    """Require every actor resource that ships in the PCK to be imported, as intended.

    The PCK-only actor files (the face masks, the equipment URI textures) are
    read through ResourceLoader, which in an export finds them only as
    imported resources. A stale .gdignore or a partial import would otherwise
    ship a client whose faces render without their masks, or whose equipment
    falls back to raw JPEG decodes; a URI texture imported without VRAM
    compression or mipmaps, or a glTF imported after all, would ship the wrong
    thing. Called on the build worktree, so the repository root is the
    project's parent.
    """
    build_dir = project.parent
    shipping = actor_shipping(build_dir)
    failures: list[str] = []
    checked = 0
    for folder in sorted(shipping["pck_folders"]):
        if (build_dir / folder / ".gdignore").exists():
            failures.append(f"{folder}: .gdignore keeps it out of the import")
    wanted = dict(URI_TEXTURE_IMPORT_PARAMS)
    for relative in sorted(shipping["pck"]):
        local = PurePosixPath(relative).relative_to("godot-client").as_posix()
        if local.endswith(PLAIN_EXPORT_SUFFIXES):
            continue  # exported as plain files by the include filter
        checked += 1
        sidecar = project / (local + ".import")
        if not sidecar.is_file():
            failures.append(f"{local}: missing .import remap")
            continue
        products = _import_products(sidecar)
        if not products or any(not (project / PurePosixPath(p)).is_file()
                               or (project / PurePosixPath(p)).stat().st_size == 0
                               for p in products):
            failures.append(f"{local}: imported resource is missing")
        if relative in shipping["uri_textures"]:
            importer, params = _import_settings(sidecar)
            wrong = [k for k in ("compress/mode", "mipmaps/generate") if params.get(k) != wanted[k]]
            if importer != "texture" or wrong:
                failures.append(f"{local}: imported as {importer or '?'} with "
                                f"{', '.join(f'{k}={params.get(k)}' for k in wrong) or 'other settings'}, "
                                "not a VRAM-compressed, mipmapped texture")
    skipped = 0
    for relative in pck_folder_others(build_dir, shipping):
        local = PurePosixPath(relative).relative_to("godot-client").as_posix()
        sidecar = project / (local + ".import")
        if sidecar.is_file() and _import_settings(sidecar)[0] == "skip":
            skipped += 1
        else:
            failures.append(f"{local}: imported, but it ships loose or nowhere")
    if not shipping["pck_folders"]:
        failures.append("no actor folder ships in the PCK; the face masks would be missing")
    if failures:
        raise PackageError("PCK actor imports are incomplete:\n  " + "\n  ".join(failures[:40]))
    log(f"checked {checked} imported actor resources ({len(shipping['uri_textures'])} URI textures) in "
        f"{', '.join(PurePosixPath(f).name for f in sorted(shipping['pck_folders']))}, "
        f"{skipped} files there skipped; {len(shipping['loose_folders'])} actor folders ship loose only")


def export_project(godot: Path, project: Path, app_dir: Path, logs: Path, platform: dict) -> None:
    log(f"exporting ({platform['preset']})")
    app_dir.mkdir(parents=True, exist_ok=True)
    text = run_godot(godot, ["--headless", "--path", str(project), "--export-release",
                             platform["preset"], str(app_dir / platform["binary"])],
                     logs / "export.log", timeout=3600)
    for name in (platform["binary"], "Eloria.pck"):
        if not (app_dir / name).is_file():
            raise PackageError(f"export did not write {name}; log: {logs / 'export.log'}\n{text[-2000:]}")


# --- staging -----------------------------------------------------------------

def copy_file(source: Path, target: Path) -> int:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return source.stat().st_size


def stage_loose_client_files(build_dir: Path, app_dir: Path) -> None:
    # Actor files ship once: the PCK-only ones (face masks, equipment URI
    # textures) and the dropped images stay out of app/.
    shipping = actor_shipping(build_dir)
    loose_actors = shipping["loose"]
    total = staged = pck_only = dropped = dropped_bytes = 0
    files = tracked(build_dir, "godot-client/assets", "godot-client/data", "godot-client/schemas")
    for relative in files:
        if relative.endswith((".import", ".report.json")):
            continue
        if relative.startswith(ACTOR_ROOT + "/") and relative not in loose_actors:
            if relative in shipping["dropped"]:
                dropped += 1
                dropped_bytes += (build_dir / relative).stat().st_size
            else:
                pck_only += 1
            continue
        total += copy_file(build_dir / relative, app_dir / PurePosixPath(relative).relative_to("godot-client"))
        staged += 1
    log(f"staged {staged} loose client files ({total / 1e9:.2f} GB); "
        f"{pck_only} actor files ship in the PCK only; {dropped} unnamed actor images "
        f"({dropped_bytes / 1e6:.0f} MB) ship nowhere")


def pck_paths(pck: Path) -> set[str]:
    """Every path in a Godot 4 PCK's directory (formats 2 to 4), without res://."""
    with open(pck, "rb") as handle:
        if handle.read(4) != b"GDPC":
            raise PackageError(f"{pck} is not a Godot PCK")
        version = struct.unpack("<4I", handle.read(16))[0]
        flags = 0
        directory = None
        if version >= 2:
            flags, = struct.unpack("<I", handle.read(4))
            handle.read(8)  # file base
        if version >= 3:
            directory, = struct.unpack("<Q", handle.read(8))
        handle.read(16 * 4)
        if directory is not None:
            handle.seek(directory)
        if flags & 1:
            raise PackageError(f"{pck} has an encrypted directory")
        count, = struct.unpack("<I", handle.read(4))
        paths = set()
        for _ in range(count):
            length, = struct.unpack("<I", handle.read(4))
            name = handle.read(length).rstrip(b"\0").decode("utf-8", "replace")
            handle.read(16 + 16 + (4 if version >= 2 else 0))  # offset, size, md5, flags
            paths.add(name.removeprefix("res://"))
    return paths


def check_actor_pack(build_dir: Path, app_dir: Path) -> None:
    """Each actor file is in exactly one place - the PCK or app/assets - or, if dropped, in none.

    The PCK must hold every PCK-only actor resource (as its .import remap and
    the imported product it names or, for .json/.bin, the file itself) and no
    other actor entry; app/assets must hold every loose file and no other
    actor file.
    """
    shipping = actor_shipping(build_dir)
    paths = pck_paths(app_dir / "Eloria.pck")
    project = build_dir / "godot-client"
    problems: list[str] = []
    expected: set[str] = set()
    for relative in sorted(shipping["pck"]):
        local = PurePosixPath(relative).relative_to("godot-client").as_posix()
        entry = local if local.endswith(PLAIN_EXPORT_SUFFIXES) else local + ".import"
        expected.add(entry)
        if entry not in paths:
            problems.append(f"{local}: not in the PCK")
        elif entry.endswith(".import"):
            sidecar = project / entry
            products = _import_products(sidecar) if sidecar.is_file() else []
            if not products or any(p not in paths for p in products):
                problems.append(f"{local}: its imported product is not in the PCK")
        if (app_dir / local).exists():
            problems.append(f"{local}: also staged loose")
    # An imported file reaches the PCK with its remap under its own path, so
    # anything else under assets/actors in the PCK leaked into the import.
    actor_prefix = PurePosixPath(ACTOR_ROOT).relative_to("godot-client").as_posix() + "/"
    leaked = sorted(p for p in paths if p.startswith(actor_prefix) and p not in expected)
    problems.extend(f"{p}: an actor file that ships loose or nowhere is in the PCK" for p in leaked[:20])
    for relative in sorted(shipping["loose"]):
        if not (app_dir / PurePosixPath(relative).relative_to("godot-client")).is_file():
            problems.append(f"{relative}: not staged loose")
    for relative in sorted(shipping["dropped"]):
        if (app_dir / PurePosixPath(relative).relative_to("godot-client")).exists():
            problems.append(f"{relative}: a dropped image was staged loose")
    if problems:
        raise PackageError(f"{len(problems)} actor files are not shipped exactly once:\n  "
                           + "\n  ".join(problems[:40]))
    log(f"checked actor files: {len(shipping['pck'])} in the PCK only "
        f"({len(shipping['uri_textures'])} URI textures), {len(shipping['loose'])} loose only, "
        f"{len(shipping['dropped'])} dropped")


def is_shipped_map_file(relative: PurePosixPath) -> bool:
    if any(part in MAP_EXCLUDED_DIRS for part in relative.parts[:-1]):
        return False
    name = relative.name
    if relative.suffix.lower() in MAP_EXCLUDED_SUFFIXES or name == ".gitignore":
        return False
    if MAP_LOD_PACKAGE.match(name):
        return False
    return not (name.endswith(".validator.json") or name.endswith("report.json"))


def json_strings(value, skip: set[str], key: str = ""):
    if isinstance(value, dict):
        for child_key, child in value.items():
            if child_key not in skip:
                yield from json_strings(child, skip, child_key)
    elif isinstance(value, list):
        for child in value:
            yield from json_strings(child, skip, key)
    elif isinstance(value, str):
        yield key, value


def shipped_eloria_assets(build_dir: Path) -> tuple[set[str], list[str], list[str]]:
    """The eloria-assets files a package ships: (files, errors, warnings).

    Every map package's shipped files, every file the client names, and the
    closure of the files those manifests name.
    """
    all_tracked = set(tracked(build_dir, "eloria-assets"))
    wanted: set[str] = set()
    package_dirs = {str(PurePosixPath(p).parent) for p in all_tracked
                    if p.startswith("eloria-assets/maps/") and p.endswith("/world.json")}
    for path in all_tracked:
        for package in package_dirs:
            if path.startswith(package + "/"):
                if is_shipped_map_file(PurePosixPath(path).relative_to(package)):
                    wanted.add(path)
                break

    # Literal references from the client: registry, cartography, scripts.
    errors: list[str] = []
    warnings: list[str] = []
    client_sources = tracked(build_dir, "godot-client/data", "godot-client/src")
    for relative in client_sources:
        if not relative.endswith((".json", ".gd")):
            continue
        text = (build_dir / relative).read_text(encoding="utf-8", errors="replace")
        for match in ASSET_REF.finditer(text):
            target = match.group(1).rstrip("/")
            if MAP_LOD_PACKAGE.match(PurePosixPath(target).name):
                continue
            if target in all_tracked:
                wanted.add(target)
            elif not any(p.startswith(target + "/") for p in all_tracked):
                (errors if relative.endswith(".json") else warnings).append(
                    f"{relative} names {target}, which is not in the commit")

    # Files a shipped manifest names, relative to the manifest. Follow the
    # closure, since a pulled-in JSON can name more files.
    queue = sorted(p for p in wanted if p.endswith(".json"))
    seen: set[str] = set()
    while queue:
        manifest = queue.pop()
        if manifest in seen:
            continue
        seen.add(manifest)
        try:
            data = json.loads((build_dir / manifest).read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        base = PurePosixPath(manifest).parent
        is_world = manifest.endswith("/world.json")
        for key, value in json_strings(data, MANIFEST_SKIPPED_KEYS):
            match = ASSET_REF.search(value)
            if match:
                target = match.group(1)
            elif FILE_LIKE.match(value) and not value.startswith(("res://", "user://", "/")):
                target = os.path.normpath(str(base / value)).replace("\\", "/")
            else:
                continue
            if MAP_LOD_PACKAGE.match(PurePosixPath(target).name):
                continue
            if target in all_tracked:
                if target not in wanted:
                    wanted.add(target)
                    if target.endswith(".json"):
                        queue.append(target)
            elif is_world and key in {"glb", "binary", "image", "file"}:
                errors.append(f"{manifest} {key} -> {target} is not in the commit")
            elif is_world:
                warnings.append(f"{manifest} {key} -> {target} not found")
        # externalResources names its files as keys (URI -> sha256), relative
        # to the GLB, so the value walk above never sees them: the continent's
        # shared images (_continent/shared-assets, in no package folder of
        # their own) were left out, and the client refuses a chunk whose
        # external images are missing (WorldManifest.verify_external_resources).
        resources = data.get("externalResources") if is_world and isinstance(data, dict) else None
        if isinstance(resources, dict):
            glb_dir = base / PurePosixPath(str(data.get("asset", {}).get("glb", "world.glb"))).parent
            for uri in resources:
                target = os.path.normpath(str(glb_dir / str(uri))).replace("\\", "/")
                if target in all_tracked:
                    wanted.add(target)
                else:
                    errors.append(f"{manifest} externalResources -> {target} is not in the commit")

    return wanted, errors, warnings


def stage_eloria_assets(build_dir: Path, stage: Path) -> list[str]:
    """Copy map packages and every eloria-assets file the client names.

    Returns warnings; raises when a reference the client will open is missing.
    """
    wanted, errors, warnings = shipped_eloria_assets(build_dir)
    if errors:
        raise PackageError("missing map files:\n  " + "\n  ".join(errors[:40]))
    total = sum(copy_file(build_dir / p, stage / p) for p in sorted(wanted))
    package_dirs = {str(PurePosixPath(p).parent) for p in tracked(build_dir, "eloria-assets/maps")
                    if p.endswith("/world.json")}
    log(f"staged {len(wanted)} eloria-assets files from {len(package_dirs)} map packages "
        f"({total / 1e9:.2f} GB)")
    return warnings


def check_glb_textures(app_dir: Path) -> None:
    """Every image a shipped glTF names by URI is loose beside it or imported in the PCK.

    GLTFDocument asks ResourceLoader for the image at the glTF's relative
    path first (res:// in an export, so the PCK's import), then reads the
    file there.
    """
    pck = app_dir / "Eloria.pck"
    packed = pck_paths(pck) if pck.is_file() else set()
    missing: list[str] = []
    count = imported = 0
    for gltf in sorted((*(app_dir / "assets").rglob("*.glb"), *(app_dir / "assets").rglob("*.gltf"))):
        for uri in gltf_image_uris(gltf):
            count += 1
            target = gltf.parent / uri
            local = posixpath.normpath(target.relative_to(app_dir).as_posix())
            if local + ".import" in packed:
                imported += 1
            elif not target.is_file():
                missing.append(f"{gltf.relative_to(app_dir).as_posix()} -> {uri}")
    if missing:
        raise PackageError(f"{len(missing)} glTF textures missing:\n  " + "\n  ".join(missing[:40]))
    log(f"checked {count} external glTF textures: {imported} imported in the PCK, "
        f"{count - imported} loose")


def check_registry(build_dir: Path, stage: Path) -> None:
    registry = json.loads((build_dir / "godot-client/data/maps/registry.json").read_text(encoding="utf-8"))
    missing = []
    for map_id, entry in registry.get("maps", {}).items():
        match = ASSET_REF.search(str(entry.get("manifest", "")))
        if match and not (stage / match.group(1)).is_file():
            missing.append(f"{map_id}: {match.group(1)}")
    if missing:
        raise PackageError("registry manifests missing from package:\n  " + "\n  ".join(missing))
    log(f"checked {len(registry.get('maps', {}))} registry maps")


VRAM_SELF_TEST_OK = "vram_textures self_test ok"


def stage_vram_textures(build_dir: Path, stage: Path, godot: Path, cache: Path, logs: Path,
                        tool: Path | None = None) -> dict:
    """Build the VRAM-compressed sidecars of the shared map images into the stage.

    The sidecars are not tracked (eloria-assets/maps/**/shared-assets/vram/ is
    ignored), so stage_eloria_assets never copies them: they are made here, by
    the commit's own tools/build_vram_textures.py, from the build worktree's
    images, straight into <stage>/eloria-assets/maps/.../vram, with a
    persistent encode cache outside every repository. Only index.json and the
    .evt files ship; the quality report goes to the logs.
    """
    tool = tool or build_dir / "godot-client" / "tools" / "build_vram_textures.py"
    log("building VRAM texture sidecars")
    cache.mkdir(parents=True, exist_ok=True)
    started = time.time()
    with open(logs / "vram-textures.log", "w", encoding="utf-8", errors="replace") as handle:
        result = subprocess.run([sys.executable, str(tool), "--maps", str(build_dir / "eloria-assets" / "maps"),
                                 "--out-root", str(stage / "eloria-assets" / "maps"), "--cache", str(cache),
                                 "--godot", str(godot)],
                                stdout=handle, stderr=subprocess.STDOUT, timeout=3600,
                                env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    text = (logs / "vram-textures.log").read_text(encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise PackageError(f"build_vram_textures.py failed; log: {logs / 'vram-textures.log'}\n{text[-2000:]}")
    files = 0
    size = 0
    for report in (stage / "eloria-assets").rglob("vram/report.json"):
        target = logs / ("vram-report-" + report.parent.parent.name + ".json")
        shutil.move(str(report), target)
    for path in (stage / "eloria-assets").rglob("vram/*"):
        if path.is_file():
            files += 1
            size += path.stat().st_size
    log(f"staged {files} VRAM sidecar files ({size / 1e6:.0f} MB, already zstd: the zip grows by about "
        f"as much) in {time.time() - started:.0f} s")
    return {"files": files, "bytes": size}


def check_vram_textures(stage: Path) -> None:
    """Every external map image a staged manifest names is staged, has a
    sidecar or a reason it has none, and every staged sidecar is the file its
    index names, byte for byte."""
    import hashlib
    problems: list[str] = []
    indexes: dict[Path, dict] = {}
    checked = 0
    for manifest_path in (stage / "eloria-assets").rglob("world.json"):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        resources = manifest.get("externalResources") or {}
        if not isinstance(resources, dict) or "streamingChunks" in manifest:
            continue
        base = (manifest_path.parent / str(manifest.get("asset", {}).get("glb", "world.glb"))).parent
        for uri, sha in resources.items():
            image = (base / uri).resolve()
            if not image.is_file():
                problems.append(f"{manifest_path.relative_to(stage)}: external image {uri} is not in the package")
                continue
            if image.parent not in indexes:
                index_path = image.parent / "vram" / "index.json"
                indexes[image.parent] = (json.loads(index_path.read_text(encoding="utf-8"))
                                         if index_path.is_file() else {})
            index = indexes[image.parent]
            checked += 1
            if sha not in index.get("images", {}) and sha not in index.get("excluded", {}):
                problems.append(f"{image.relative_to(stage)}: no sidecar and no exclusion reason")
    sidecars = 0
    for directory, index in indexes.items():
        for sha, entry in index.get("images", {}).items():
            path = directory / "vram" / entry["file"]
            if not path.is_file():
                problems.append(f"{path.relative_to(stage)}: listed in the index but missing")
                continue
            sidecars += 1
            if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
                problems.append(f"{path.relative_to(stage)}: sha256 differs from the index")
        listed = {entry["file"] for entry in index.get("images", {}).values()}
        for path in (directory / "vram").glob("*"):
            if path.name != "index.json" and path.name not in listed:
                problems.append(f"{path.relative_to(stage)}: not named by the index")
    if problems:
        raise PackageError(f"{len(problems)} VRAM sidecar problems:\n  " + "\n  ".join(problems[:40]))
    log(f"checked VRAM sidecars: {checked} external image references, {sidecars} sidecars")


def wsl_path(path: Path) -> str:
    resolved = path.resolve()
    return f"/mnt/{resolved.drive[0].lower()}{resolved.as_posix()[2:]}"


def smoke_launch(app_dir: Path, logs: Path, platform: dict, vram_textures: bool = False) -> None:
    # The launch must leave the package exactly as it was: a user:// that
    # falls back to a relative path writes settings and caches into app/,
    # and they would ship in the archive.
    #
    # With sidecars staged it also proves the shipped binary decodes one: the
    # client logs VramTextures.self_test() when ELORIA_VRAM_SELF_TEST=1. The
    # launch is headless, so this covers the decode, not the GPU upload.
    before = {p for p in app_dir.parent.rglob("*")}
    try:
        text = _launch(app_dir, logs, platform, vram_textures)
        if vram_textures and text is not None and VRAM_SELF_TEST_OK not in text:
            lines = [line for line in text.splitlines() if "vram_textures" in line]
            raise PackageError("the exported client did not decode a VRAM sidecar:\n  "
                               + "\n  ".join(lines[:10] or ["(no vram_textures line)"])
                               + f"\nfull log: {logs / 'smoke.log'}")
    finally:
        added = sorted(p for p in app_dir.parent.rglob("*") if p not in before)
        if added:
            raise PackageError("the smoke launch wrote into the package:\n  "
                               + "\n  ".join(str(p.relative_to(app_dir.parent)) for p in added[:20]))


def _launch(app_dir: Path, logs: Path, platform: dict, vram_textures: bool = False) -> str | None:
    self_test = "ELORIA_VRAM_SELF_TEST=1 " if vram_textures else ""
    if platform["binary"].endswith(".exe"):
        log("smoke launch (headless)")
        with tempfile.TemporaryDirectory(prefix="eloria-smoke-") as appdata:
            # A throwaway APPDATA keeps user:// away from the real client settings.
            env = dict(os.environ, APPDATA=appdata, LOCALAPPDATA=appdata)
            if vram_textures:
                env["ELORIA_VRAM_SELF_TEST"] = "1"
            text = run_godot(app_dir / platform["binary"], ["--headless", "--quit-after", "600"],
                             logs / "smoke.log", timeout=300, env=env)
    else:
        # The Linux binary runs under WSL, with a throwaway HOME for user://.
        wsl = shutil.which("wsl.exe") or shutil.which("wsl")
        if not wsl or subprocess.run([wsl, "-d", WSL_DISTRO, "--exec", "true"],
                                     capture_output=True).returncode != 0:
            log(f"smoke launch skipped: WSL distribution {WSL_DISTRO} is not available")
            return None
        log(f"smoke launch (headless, WSL {WSL_DISTRO})")
        command = (f'home=$(mktemp -d) && cd "{wsl_path(app_dir)}" && '
                   f'HOME="$home" XDG_DATA_HOME="$home" XDG_CONFIG_HOME="$home" {self_test}'
                   f'./{platform["binary"]} --headless --quit-after 600; '
                   f'status=$?; rm -rf "$home"; exit $status')
        # --exec, not --: "--" hands the line to the distro's login shell
        # first, which expands $home to nothing before sh ever sees it.
        text = run_godot(Path(wsl), ["-d", WSL_DISTRO, "--exec", "sh", "-c", command],
                         logs / "smoke.log", timeout=300)
    hits = [line for line in text.splitlines() if any(f in line for f in SMOKE_FAILURES)]
    if hits:
        raise PackageError("the exported client reported errors at startup:\n  "
                           + "\n  ".join(hits[:30]) + f"\nfull log: {logs / 'smoke.log'}")
    return text


def default_server(build_dir: Path) -> tuple[str, str]:
    scene = (build_dir / "godot-client/src/app/main.tscn").read_text(encoding="utf-8")
    host = re.search(r'\[node name="Host"[^\]]*\]\s*(?:[^\[]*?)text = "([^"]*)"', scene)
    port = re.search(r'\[node name="Port"[^\]]*\]\s*(?:[^\[]*?)value = ([0-9.]+)', scene)
    return (host.group(1) if host else "?", str(int(float(port.group(1)))) if port else "2000")


def write_launchers(stage: Path, server: str | None, build_dir: Path, version: str,
                    platform: dict) -> list[str]:
    args = []
    if server:
        host, _, port = server.partition(":")
        args = [f"--server={host}"] + ([f"--port={port}"] if port else [])
        shown_host, shown_port = host, port or default_server(build_dir)[1]
    else:
        shown_host, shown_port = default_server(build_dir)
    extra = (" -- " + " ".join(args)) if args else ""
    if not platform["binary"].endswith(".exe"):
        (stage / "Eloria.sh").write_text(
            '#!/bin/sh\n'
            'cd "$(dirname "$0")/app" || exit 1\n'
            f'exec ./{platform["binary"]}{extra} "$@"\n', encoding="ascii", newline="\n")
        (stage / "Eloria-debug.sh").write_text(
            '#!/bin/sh\n'
            'cd "$(dirname "$0")/app" || exit 1\n'
            'echo "Eloria is running; its log is saved as eloria-debug.log beside this script."\n'
            f'./{platform["binary"]} --verbose --log-file ../eloria-debug.log{extra} "$@"\n'
            'status=$?\n'
            'echo "Eloria exited with status $status."\n'
            'exit $status\n', encoding="ascii", newline="\n")
        (stage / "README.txt").write_text(
            README_LINUX.format(version=version, host=shown_host, port=shown_port,
                                archive=f"{stage.name}.tar.gz", folder=stage.name, binary=platform["binary"]),
            encoding="utf-8", newline="\n")
        return args
    (stage / "Eloria.bat").write_text(
        f'@echo off\r\nstart "" "%~dp0app\\Eloria.exe"{extra}\r\n', encoding="ascii")
    # The installed export templates carry no console wrapper, and a GUI exe
    # prints nothing to the window that started it, so the log goes to a file
    # that is shown once the game exits.
    (stage / "Eloria (debug console).bat").write_text(
        '@echo off\r\ncd /d "%~dp0app"\r\n'
        'echo Eloria is running; its log will appear here when it exits.\r\n'
        f'Eloria.exe --verbose --log-file "%~dp0eloria-debug.log"{extra}\r\n'
        'type "%~dp0eloria-debug.log"\r\n'
        'echo.\r\necho The log is saved as eloria-debug.log. Press any key to close this window.\r\n'
        'pause >nul\r\n',
        encoding="ascii")
    (stage / "README.txt").write_text(README.format(version=version, host=shown_host, port=shown_port),
                                      encoding="utf-8", newline="\r\n")
    return args


README = """Eloria - Windows Client
=======================
Build {version}

Requirements
------------
Windows 10 or 11, 64-bit, and a GPU from the last decade. The game draws with
Vulkan; on a GPU or driver without it, it starts in a simpler OpenGL 3.3 mode
that looks flatter but plays the same.

Install
-------
From the zip: unzip the whole folder anywhere (no admin rights needed) and
double-click Eloria.bat. Keep the folder together - the game reads the app and
eloria-assets folders that sit beside it.

From the installer: run it and start Eloria from the Start menu.

The first time you run it, Windows SmartScreen may say "Windows protected your
PC" because the program is not code-signed. Click "More info", then "Run
anyway".

Playing
-------
The login screen is pre-filled with the server:

    Host: {host}
    Port: {port}

Enter a username and password and press Connect, or create a character.

What is in this folder
----------------------
  Eloria.bat                    Start the game.
  Eloria (debug console).bat    Start with a log window, for troubleshooting.
  app\\                          The game executable and its data.
  eloria-assets\\                World maps and region artwork.

Troubleshooting
---------------
Nothing happens when I start it
    Run "Eloria (debug console).bat". It keeps a window open with the error.

It cannot connect
    Check that outbound TCP to the port above is not blocked by a firewall.

The world is black or models are missing
    Part of the folder is missing or was moved. Unzip or install it again.
"""


README_LINUX = """Eloria - Linux Client
=====================
Build {version}

Requirements
------------
64-bit x86 Linux with a desktop session (X11, or Wayland with XWayland) and
a GPU driver supporting Vulkan - any recent Mesa, NVIDIA or AMD driver. With
only OpenGL 3.3 the game starts in a simpler mode that looks flatter but plays
the same. Nothing else needs installing.

Install
-------
Extract the whole folder anywhere you can write to, for example:

    tar -xzf {archive} -C ~/Games

then start the game:

    ~/Games/{folder}/Eloria.sh

Keep the folder together - the game reads the app and eloria-assets folders
that sit beside the scripts. If your desktop does not run .sh files on
double-click, start it from a terminal as above.

If Eloria.sh says "Permission denied", the archive was extracted by a tool
that dropped file permissions. Fix it with:

    chmod +x Eloria.sh Eloria-debug.sh app/{binary}

Playing
-------
The login screen is pre-filled with the server:

    Host: {host}
    Port: {port}

Enter a username and password and press Connect, or create a character.

What is in this folder
----------------------
  Eloria.sh          Start the game.
  Eloria-debug.sh    Start with verbose logging to eloria-debug.log.
  app/               The game executable and its data.
  eloria-assets/     World maps and region artwork.

Troubleshooting
---------------
Nothing happens when I start it
    Run ./Eloria-debug.sh from a terminal and read eloria-debug.log.

It cannot connect
    Check that outbound TCP to the port above is not blocked by a firewall.

The world is black or models are missing
    Part of the folder is missing or was moved. Extract it again.
"""


# --- outputs ------------------------------------------------------------------

def make_tarball(stage: Path, platform: dict) -> Path:
    """A .tar.gz, because a zip made on Windows cannot mark files executable."""
    archive = stage.parent / f"{stage.name}.tar.gz"
    archive.unlink(missing_ok=True)
    executables = {platform["binary"], "Eloria.sh", "Eloria-debug.sh"}
    log(f"archiving {archive.name}")

    def normalise(info: tarfile.TarInfo) -> tarfile.TarInfo | None:
        if Path(info.name).name == MARKER:
            return None
        info.uid = info.gid = 0
        info.uname = info.gname = ""
        info.mode = 0o755 if info.isdir() or Path(info.name).name in executables else 0o644
        return info

    with tarfile.open(archive, "w:gz", compresslevel=1) as handle:
        handle.add(stage, arcname=stage.name, filter=normalise)
    return archive


def make_zip(stage: Path) -> Path:
    archive = stage.with_suffix(".zip")
    archive.unlink(missing_ok=True)
    seven = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "7-Zip" / "7z.exe"
    log(f"zipping {archive.name}")
    if seven.is_file():
        result = subprocess.run([str(seven), "a", "-tzip", "-mx=1", "-bso0", "-bsp0",
                                 str(archive), stage.name, f"-xr!{MARKER}"], cwd=stage.parent)
        if result.returncode != 0:
            raise PackageError("7-Zip failed")
    else:
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as handle:
            for path in sorted(stage.rglob("*")):
                if path.is_file() and path.name != MARKER:
                    handle.write(path, path.relative_to(stage.parent))
    return archive


def make_installer(stage: Path, iscc: Path, version: str, launch_args: list[str], logs: Path) -> Path:
    size = sum(p.stat().st_size for p in stage.rglob("*") if p.is_file())
    parameters = " ".join(launch_args).replace('"', '""')
    spanning = size > 1_800_000_000
    script = f"""; Generated by godot-client/tools/package_client.py
[Setup]
AppId={INSTALLER_APP_ID.replace('{', '{{')}
AppName=Eloria
AppVersion={version}
AppPublisher=Eloria
DefaultDirName={{localappdata}}\\Programs\\Eloria
DefaultGroupName=Eloria
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={stage.parent}
OutputBaseFilename={stage.name}-setup
Compression=lzma2/fast
SolidCompression=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={{app}}\\app\\Eloria.exe
{"DiskSpanning=yes" + chr(10) + "DiskSliceSize=max" if spanning else ""}

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[InstallDelete]
; An upgrade replaces the game data wholesale so files a newer build dropped
; do not linger.
Type: filesandordirs; Name: "{{app}}\\app"
Type: filesandordirs; Name: "{{app}}\\eloria-assets"

[Files]
Source: "{stage}\\*"; DestDir: "{{app}}"; Excludes: "{MARKER}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{{group}}\\Eloria"; Filename: "{{app}}\\app\\Eloria.exe"; Parameters: "{('-- ' + parameters) if parameters else ''}"; WorkingDir: "{{app}}\\app"
Name: "{{group}}\\Eloria (debug console)"; Filename: "{{app}}\\Eloria (debug console).bat"; WorkingDir: "{{app}}\\app"
Name: "{{userdesktop}}\\Eloria"; Filename: "{{app}}\\app\\Eloria.exe"; Parameters: "{('-- ' + parameters) if parameters else ''}"; WorkingDir: "{{app}}\\app"; Tasks: desktopicon

[Run]
Filename: "{{app}}\\app\\Eloria.exe"; Parameters: "{('-- ' + parameters) if parameters else ''}"; WorkingDir: "{{app}}\\app"; Description: "Start Eloria"; Flags: nowait postinstall skipifsilent
"""
    iss = logs / "eloria.iss"
    iss.write_text(script, encoding="utf-8-sig")
    log("compiling installer" + (" (disk-spanned: setup exe + .bin slices)" if spanning else ""))
    with open(logs / "iscc.log", "w", encoding="utf-8", errors="replace") as handle:
        result = subprocess.run([str(iscc), str(iss)], stdout=handle, stderr=subprocess.STDOUT)
    if result.returncode != 0:
        raise PackageError(f"ISCC failed; log: {logs / 'iscc.log'}")
    return stage.parent / f"{stage.name}-setup.exe"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--platform", choices=sorted(PLATFORMS), default="windows",
                        help="windows: folder + zip; linux: folder + tar.gz (default windows)")
    parser.add_argument("--ref", default="origin/develop", help="commit to package (default origin/develop)")
    parser.add_argument("--no-fetch", action="store_true", help="do not fetch origin first")
    parser.add_argument("--godot", help="Godot console exe (default: the one in the client checkout)")
    parser.add_argument("--build-dir", type=Path, default=DIST / ".build" / "client-src",
                        help="persistent build worktree (default dist/.build/client-src)")
    parser.add_argument("--out", type=Path, default=DIST, help="output folder (default eloria-project/dist)")
    parser.add_argument("--server", help="bake HOST[:PORT] into the launchers instead of the login default")
    parser.add_argument("--force", action="store_true", help="replace an existing package for this commit")
    parser.add_argument("--no-smoke", action="store_true", help="skip the headless launch check")
    parser.add_argument("--no-vram-textures", action="store_true",
                        help="ship no VRAM-compressed map texture sidecars (the client decodes every image)")
    parser.add_argument("--vram-cache", type=Path, default=DIST / ".build" / "vram-cache",
                        help="encode cache for the sidecars (default dist/.build/vram-cache)")
    parser.add_argument("--no-zip", action="store_true", help="leave the folder unarchived")
    parser.add_argument("--installer", action="store_true", help="also build an Inno Setup installer")
    parser.add_argument("--iscc", help="path to Inno Setup's ISCC.exe")
    options = parser.parse_args()

    started = time.time()
    platform = PLATFORMS[options.platform]
    try:
        if options.installer and options.platform != "windows":
            raise PackageError("--installer builds a Windows installer only")
        godot = find_godot(options.godot)
        iscc = find_iscc(options.iscc) if options.installer else None
        if options.installer and iscc is None:
            raise PackageError("--installer needs Inno Setup 6 (ISCC.exe); install it from "
                               "https://jrsoftware.org/isdl.php or pass --iscc")
        if not options.no_fetch and options.ref.startswith("origin/"):
            log("fetching origin")
            git("fetch", "-q", "origin")
        sha = git("rev-parse", "--verify", options.ref + "^{commit}").strip()
        stamp = datetime.date.today().strftime("%Y%m%d")
        version = f"{stamp}-{sha[:9]}"
        stage = options.out.resolve() / f"{platform['folder']}-{version}"
        log(f"packaging {options.ref} = {sha[:9]} into {stage}")
        if stage.exists():
            if not options.force:
                raise PackageError(f"{stage} already exists; pass --force to rebuild it")
            if not (stage / MARKER).is_file():
                raise PackageError(f"{stage} was not made by this script; refusing to delete it")
            shutil.rmtree(stage)
        logs = options.out.resolve() / ".build" / "logs" / f"{options.platform}-{version}"
        logs.mkdir(parents=True, exist_ok=True)
        stage.mkdir(parents=True)
        (stage / MARKER).write_text(sha + "\n", encoding="utf-8")

        build_dir = options.build_dir.resolve()
        project = prepare_build_tree(build_dir, sha)
        import_project(godot, project, logs)
        check_actor_imports(project)
        app_dir = stage / "app"
        export_project(godot, project, app_dir, logs, platform)
        stage_loose_client_files(build_dir, app_dir)
        check_actor_pack(build_dir, app_dir)
        warnings = stage_eloria_assets(build_dir, stage)
        if not options.no_vram_textures:
            stage_vram_textures(build_dir, stage, godot, options.vram_cache.resolve(), logs)
            check_vram_textures(stage)
        check_registry(build_dir, stage)
        check_glb_textures(app_dir)
        launch_args = write_launchers(stage, options.server, build_dir, version, platform)
        if not options.no_smoke:
            smoke_launch(app_dir, logs, platform, vram_textures=not options.no_vram_textures)

        outputs = [stage]
        if not options.no_zip:
            outputs.append(make_zip(stage) if options.platform == "windows" else make_tarball(stage, platform))
        if iscc:
            outputs.append(make_installer(stage, iscc, version, launch_args, logs))
    except PackageError as error:
        log(f"FAILED: {error}")
        return 1

    for warning in warnings[:20]:
        log(f"warning: {warning}")
    if len(warnings) > 20:
        log(f"... {len(warnings) - 20} more warnings")
    log(f"done in {(time.time() - started) / 60:.1f} min; logs in {logs}")
    for output in outputs:
        size = (sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
                if output.is_dir() else output.stat().st_size)
        log(f"  {output}  ({size / 1e9:.2f} GB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
