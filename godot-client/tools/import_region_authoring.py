#!/usr/bin/env python3
"""Import one certified legacy territory into the saved authoring framework.

The region spec selects an explicit adapter.  There is deliberately no
default adapter: a territory with different content or crossing semantics
must declare and implement those differences instead of inheriting Sunmane.
"""
from __future__ import annotations

import argparse
import importlib
from pathlib import Path
import sys


REPO = Path(__file__).resolve().parents[2]
CONTINENT = REPO / "eloria-assets/maps/nymara-regions/_continent"
if str(CONTINENT) not in sys.path:
    sys.path.insert(0, str(CONTINENT))
import authoring_catalog as catalog


ADAPTERS = {
    "amethyst-v1": "import_amethyst_authoring",
    "sunmane-v1": "import_sunmane_authoring",
}


def arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region-spec", type=Path, required=True)
    parser.add_argument("--source-world", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--roads", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--base-heights", type=Path, required=True)
    parser.add_argument("--resolved-heights", type=Path, required=True)
    parser.add_argument("--runtime-bindings", type=Path, required=True)
    parser.add_argument("--runtime-profile-root", type=Path, required=True)
    parser.add_argument("--composed", type=Path)
    parser.add_argument("--composition", type=Path)
    parser.add_argument("--export-ledger", type=Path)
    parser.add_argument("--published-master", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def adapter_arguments(args: argparse.Namespace, contract: catalog.RegionContract) -> list[str]:
    output = (args.output or contract.scene_path.parent).resolve()
    if output != contract.scene_path.parent.resolve():
        raise catalog.CatalogError(
            f"--output must match the spec scene directory: {contract.scene_path.parent}")
    values = [
        "--source-world", str(args.source_world),
        "--source-manifest", str(args.source_manifest),
        "--roads", str(args.roads), "--plan", str(args.plan),
        "--base-heights", str(args.base_heights),
        "--resolved-heights", str(args.resolved_heights),
        "--runtime-bindings", str(args.runtime_bindings),
        "--runtime-profile-root", str(args.runtime_profile_root),
        "--output", str(output),
    ]
    if args.force:
        values.append("--force")
    for name in ("composed", "composition", "export_ledger", "published_master"):
        value = getattr(args, name, None)
        if value is not None:
            values += ["--" + name.replace("_", "-"), str(value)]
    return values


def main(argv: list[str] | None = None) -> int:
    args = arguments(argv)
    # Import is the one operation allowed to read a spec before its declared
    # scene exists. Catalog activation remains atomic and still requires both.
    contract = catalog.load_region_spec(args.region_spec.resolve(), require_scene=False)
    module_name = ADAPTERS.get(contract.adapter)
    if module_name is None:
        supported = ", ".join(sorted(ADAPTERS))
        raise catalog.CatalogError(
            f"{args.region_spec}: unsupported explicit adapter {contract.adapter!r}; "
            f"registered adapters: {supported}")
    module = importlib.import_module(module_name)
    return int(module.main(adapter_arguments(args, contract)))


if __name__ == "__main__":
    raise SystemExit(main())
