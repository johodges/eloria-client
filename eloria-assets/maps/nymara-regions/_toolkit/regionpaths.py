"""Locating a region package from a toolkit script.

The toolkit used to live inside `amberwood/source/`, so every script could
assume `Path(__file__).parent.parent` was the region package. It now lives in
`_toolkit/`, shared by every region, so the package has to be named instead of
inferred from the script's own location.

Resolution order: an explicit `--package`, then `$NYMARA_REGION_PACKAGE`, then
the nearest enclosing directory that looks like a region package (one holding a
`world.json`), starting from the working directory.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

TOOLKIT = Path(__file__).resolve().parent
REGIONS = TOOLKIT.parent


def looks_like_package(path: Path) -> bool:
    return (path / "world.json").is_file()


def package_root(explicit: str | os.PathLike | None = None) -> Path:
    """Return the region package directory, or raise with a usable message."""
    if explicit:
        path = Path(explicit).resolve()
        if not path.is_dir():
            raise SystemExit(f"--package is not a directory: {path}")
        return path

    env = os.environ.get("NYMARA_REGION_PACKAGE")
    if env:
        return Path(env).resolve()

    here = Path.cwd().resolve()
    for candidate in (here, *here.parents):
        if candidate == REGIONS:
            break
        if looks_like_package(candidate):
            return candidate

    raise SystemExit(
        "cannot tell which region package to act on: run from inside one, "
        "pass --package <dir>, or set NYMARA_REGION_PACKAGE")


def region_source(package: Path) -> Path:
    """The region's own build sources, which the toolkit imports for VIEWS etc."""
    return package / "source"


def load_region_views(package: Path):
    """Import the region's `source/views.py`.

    VIEWS (camera set) and PANELS (detail-board panel -> capture mapping) are
    per-region data, not toolkit data, so they live with the region that owns
    them. Kept out of the toolkit so a new region does not have to edit it.
    """
    import importlib.util

    path = region_source(package) / "views.py"
    if not path.is_file():
        raise SystemExit(f"region has no camera/panel table: {path}")
    spec = importlib.util.spec_from_file_location(
        f"_region_views_{package.name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_region_build(package: Path):
    """Import the region's build module and return its `build_region`.

    The capture and comparison tools used to `from build_amberwood import
    build_region`, which meant they could only ever capture Amberwood. Every
    region package carries exactly one `source/build_<region>.py` exposing
    `build_region`, so it is found by convention instead of by name.
    """
    import importlib.util

    source = region_source(package)
    candidates = sorted(source.glob("build_*.py"))
    # `build_interiors.py` and friends are secondary builds, not the region's
    candidates = [c for c in candidates if c.stem != "build_interiors"]
    if not candidates:
        raise SystemExit(f"no build_<region>.py in {source}")
    path = candidates[0]
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))
    spec = importlib.util.spec_from_file_location(
        f"_region_build_{package.name}", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    if not hasattr(module, "build_region"):
        raise SystemExit(f"{path} does not define build_region()")
    return module.build_region
