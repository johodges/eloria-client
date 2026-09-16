#!/usr/bin/env python3
"""Build the Windows client package that installs Eloria on another machine.

Added 2026-09-16 for Eloria Client.

    python godot-client/tools/package_windows.py              # origin/develop
    python godot-client/tools/package_windows.py --ref HEAD --installer

The package is built from a commit, never from a working tree. The main
checkout is shared with other sessions and always holds someone's unfinished
edits, so the script keeps its own detached worktree (dist/.build/client-src
beside the repositories), forces it to the commit, imports it and exports it.
Nothing it does touches the checkout it is run from.

What goes in, and why it is more than an export:

  app/Eloria.exe, Eloria.pck
      The Godot export. Scripts, scenes, UI art and data.
  app/assets, app/data, app/schemas
      Loose copies. Actor models are read with GLTFDocument from
      ProjectSettings.globalize_path("res://assets/..."), which in an exported
      build is the folder the exe sits in, not the pack - and the equipment
      GLBs reference ~1,500 textures by relative URI from that folder. None of
      it can live in the pack. (That is also why the build worktree gets a
      .gdignore in assets/actors: nothing imports those files, and skipping
      them takes the 4 GB out of the import.)
  eloria-assets/maps, eloria-assets/concepts
      "res://../eloria-assets/..." resolves beside app/. Every map package (a
      folder holding world.json) ships without its references, captures,
      sources, reports and unused world-lod2.glb; any other file a shipped
      manifest or the map registry names is pulled in even if the filter
      dropped it.

Only files tracked at the commit are shipped. Before zipping, the package is
checked - every registry manifest, the files each manifest names, and every
external texture a GLB references must be present - and the exported game is
started headless once with a throwaway APPDATA, failing on any script error.

--installer also compiles an Inno Setup installer (per-user, no admin, Start
menu shortcut, uninstaller) when ISCC.exe is available. Inno Setup is not part
of the repository: https://jrsoftware.org/isdl.php
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path, PurePosixPath

CLIENT = Path(__file__).resolve().parents[1]
REPO = CLIENT.parent
PROJECT = REPO.parent
DIST = PROJECT / "dist"
GODOT_EXE = "Godot_v4.7.2-stable_win64_console.exe"
MARKER = ".eloria-package"
PRESET_NAME = "Windows Desktop"
ASSET_REF = re.compile(r"res://\.\./(eloria-assets/[^\"'\s]+)")

# The installer's identity. Keep it fixed: Windows matches upgrades and the
# uninstaller entry on it.
INSTALLER_APP_ID = "{6B1E9F4C-3A52-4D8E-9C71-5E0B2F8A4D17}"

# Folders and files inside a map package that the client never reads.
MAP_EXCLUDED_DIRS = {"references", "captures", "godot-captures", "source",
                     "sources", "qa", "reports", "review", "renders"}
MAP_EXCLUDED_SUFFIXES = {".py", ".md", ".gd", ".c", ".txt", ".gitignore"}
# Reduced-detail map packages (world-lod2.glb, 335 MB across eleven maps).
# Manifests list them under lodGroups, but no client code loads them.
MAP_LOD_PACKAGE = re.compile(r"^world-lod\d+\.glb$")
# Manifest keys that describe provenance, or files the client never opens.
MANIFEST_SKIPPED_KEYS = {"sources", "provenance", "knownLimitations", "lodGroups"}
FILE_LIKE = re.compile(r"^[^:*?\"<>|\s]+\.(glb|gltf|bin|json|webp|png|jpg|jpeg|gz|escg|ogg|wav)$", re.I)
SMOKE_FAILURES = ("SCRIPT ERROR", "Parse Error", "Failed to load script",
                  "No loader found", "Cannot open file", "Failed loading resource")

# The export preset is not tracked, so the build writes its own. The pack
# leaves out assets/actors (read loose, see above) along with dev material.
EXPORT_PRESETS = """[preset.0]

name="Windows Desktop"
platform="Windows Desktop"
runnable=true
advanced_options=false
dedicated_server=false
custom_features=""
export_filter="all_resources"
include_filter="*.json,*.bin"
exclude_filter="Godot_v*.exe,docs/*,tests/*,tools/*,test-artifacts/*,*.md,assets/actors/*"
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
"""


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
    (project / "assets" / "actors" / ".gdignore").write_text("", encoding="utf-8")
    return project


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


def export_project(godot: Path, project: Path, app_dir: Path, logs: Path) -> None:
    log("exporting")
    app_dir.mkdir(parents=True, exist_ok=True)
    text = run_godot(godot, ["--headless", "--path", str(project), "--export-release",
                             PRESET_NAME, str(app_dir / "Eloria.exe")],
                     logs / "export.log", timeout=3600)
    for name in ("Eloria.exe", "Eloria.pck"):
        if not (app_dir / name).is_file():
            raise PackageError(f"export did not write {name}; log: {logs / 'export.log'}\n{text[-2000:]}")


# --- staging -----------------------------------------------------------------

def copy_file(source: Path, target: Path) -> int:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return source.stat().st_size


def stage_loose_client_files(build_dir: Path, app_dir: Path) -> None:
    total = 0
    files = tracked(build_dir, "godot-client/assets", "godot-client/data", "godot-client/schemas")
    for relative in files:
        if relative.endswith((".import", ".report.json")):
            continue
        total += copy_file(build_dir / relative, app_dir / PurePosixPath(relative).relative_to("godot-client"))
    log(f"staged {len(files)} loose client files ({total / 1e9:.2f} GB)")


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


def stage_eloria_assets(build_dir: Path, stage: Path) -> list[str]:
    """Copy map packages and every eloria-assets file the client names.

    Returns warnings; raises when a reference the client will open is missing.
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
            if target in all_tracked:
                if target not in wanted:
                    wanted.add(target)
                    if target.endswith(".json"):
                        queue.append(target)
            elif is_world and key in {"glb", "binary", "image", "file"}:
                errors.append(f"{manifest} {key} -> {target} is not in the commit")
            elif is_world:
                warnings.append(f"{manifest} {key} -> {target} not found")

    if errors:
        raise PackageError("missing map files:\n  " + "\n  ".join(errors[:40]))
    total = sum(copy_file(build_dir / p, stage / p) for p in sorted(wanted))
    log(f"staged {len(wanted)} eloria-assets files from {len(package_dirs)} map packages "
        f"({total / 1e9:.2f} GB)")
    return warnings


def check_glb_textures(app_dir: Path) -> None:
    missing: list[str] = []
    count = 0
    for glb in (app_dir / "assets").rglob("*.glb"):
        with open(glb, "rb") as handle:
            header = handle.read(20)
            if len(header) < 20 or header[:4] != b"glTF":
                continue
            length, _ = struct.unpack("<II", header[12:20])
            document = json.loads(handle.read(length))
        for image in document.get("images", []):
            uri = image.get("uri")
            if uri and not uri.startswith("data:"):
                count += 1
                if not (glb.parent / uri).is_file():
                    missing.append(f"{glb.relative_to(app_dir)} -> {uri}")
    if missing:
        raise PackageError(f"{len(missing)} GLB textures missing:\n  " + "\n  ".join(missing[:40]))
    log(f"checked {count} external GLB textures")


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


def smoke_launch(app_dir: Path, logs: Path) -> None:
    log("smoke launch (headless)")
    exe = app_dir / "Eloria.exe"
    with tempfile.TemporaryDirectory(prefix="eloria-smoke-") as appdata:
        # A throwaway APPDATA keeps user:// away from the real client settings.
        env = dict(os.environ, APPDATA=appdata, LOCALAPPDATA=appdata)
        text = run_godot(exe, ["--headless", "--quit-after", "600"], logs / "smoke.log",
                         timeout=300, env=env)
    hits = [line for line in text.splitlines() if any(f in line for f in SMOKE_FAILURES)]
    if hits:
        raise PackageError("the exported client reported errors at startup:\n  "
                           + "\n  ".join(hits[:30]) + f"\nfull log: {logs / 'smoke.log'}")


def default_server(build_dir: Path) -> tuple[str, str]:
    scene = (build_dir / "godot-client/src/app/main.tscn").read_text(encoding="utf-8")
    host = re.search(r'\[node name="Host"[^\]]*\]\s*(?:[^\[]*?)text = "([^"]*)"', scene)
    port = re.search(r'\[node name="Port"[^\]]*\]\s*(?:[^\[]*?)value = ([0-9.]+)', scene)
    return (host.group(1) if host else "?", str(int(float(port.group(1)))) if port else "2000")


def write_launchers(stage: Path, server: str | None, build_dir: Path, version: str) -> list[str]:
    args = []
    if server:
        host, _, port = server.partition(":")
        args = [f"--server={host}"] + ([f"--port={port}"] if port else [])
        shown_host, shown_port = host, port or default_server(build_dir)[1]
    else:
        shown_host, shown_port = default_server(build_dir)
    extra = (" -- " + " ".join(args)) if args else ""
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
Windows 10 or 11, 64-bit, and a GPU from the last decade.

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


# --- outputs ------------------------------------------------------------------

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
    script = f"""; Generated by godot-client/tools/package_windows.py
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
    parser.add_argument("--ref", default="origin/develop", help="commit to package (default origin/develop)")
    parser.add_argument("--no-fetch", action="store_true", help="do not fetch origin first")
    parser.add_argument("--godot", help="Godot console exe (default: the one in the client checkout)")
    parser.add_argument("--build-dir", type=Path, default=DIST / ".build" / "client-src",
                        help="persistent build worktree (default dist/.build/client-src)")
    parser.add_argument("--out", type=Path, default=DIST, help="output folder (default eloria-project/dist)")
    parser.add_argument("--server", help="bake HOST[:PORT] into the launchers instead of the login default")
    parser.add_argument("--force", action="store_true", help="replace an existing package for this commit")
    parser.add_argument("--no-smoke", action="store_true", help="skip the headless launch check")
    parser.add_argument("--no-zip", action="store_true", help="leave the folder unzipped")
    parser.add_argument("--installer", action="store_true", help="also build an Inno Setup installer")
    parser.add_argument("--iscc", help="path to Inno Setup's ISCC.exe")
    options = parser.parse_args()

    started = time.time()
    try:
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
        stage = options.out.resolve() / f"Eloria-Windows-{version}"
        log(f"packaging {options.ref} = {sha[:9]} into {stage}")
        if stage.exists():
            if not options.force:
                raise PackageError(f"{stage} already exists; pass --force to rebuild it")
            if not (stage / MARKER).is_file():
                raise PackageError(f"{stage} was not made by this script; refusing to delete it")
            shutil.rmtree(stage)
        logs = options.out.resolve() / ".build" / "logs" / version
        logs.mkdir(parents=True, exist_ok=True)
        stage.mkdir(parents=True)
        (stage / MARKER).write_text(sha + "\n", encoding="utf-8")

        build_dir = options.build_dir.resolve()
        project = prepare_build_tree(build_dir, sha)
        import_project(godot, project, logs)
        app_dir = stage / "app"
        export_project(godot, project, app_dir, logs)
        stage_loose_client_files(build_dir, app_dir)
        warnings = stage_eloria_assets(build_dir, stage)
        check_registry(build_dir, stage)
        check_glb_textures(app_dir)
        launch_args = write_launchers(stage, options.server, build_dir, version)
        if not options.no_smoke:
            smoke_launch(app_dir, logs)

        outputs = [stage]
        if not options.no_zip:
            outputs.append(make_zip(stage))
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
