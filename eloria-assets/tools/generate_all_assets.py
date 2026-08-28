#!/usr/bin/env python3
"""Generate the complete independent Eloria data pack with safe parallel waves."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Task:
    name: str
    scripts: tuple[str, ...]


ACTOR_CHAIN = Task("actors", (
    "generate_characters.py",
    "generate_authored_players.py",
    "generate_humanoid_enemies.py",
    "generate_fantasy_archetypes.py",
    "generate_npcs.py",
    "generate_creatures.py",
))

PARALLEL_WAVE = (
    ACTOR_CHAIN,
    Task("scenery", ("generate_scenery.py",)),
    Task("interactives", ("generate_interactives.py",)),
    Task("regions", ("generate_regions.py",)),
    Task("item-atlas", ("generate_item_atlas.py",)),
    Task("runtime", ("generate_runtime_assets.py",)),
    Task("special-events", ("generate_special_event_assets.py",)),
)


def command(script: Path, output: Path) -> list[str]:
    args = [sys.executable, str(script)]
    if script.name != "check_provenance.py":
        args.append(str(output))
    return args


def run_task(task: Task, tools_dir: Path, output: Path, repo_root: Path,
             stop: threading.Event, dry_run: bool) -> tuple[str, str]:
    logs: list[str] = []
    for script_name in task.scripts:
        if stop.is_set():
            return task.name, "cancelled after another generator failed"
        args = command(tools_dir / script_name, output)
        print(f"[{task.name}] starting {script_name}", flush=True)
        if dry_run:
            logs.append("DRY RUN: " + " ".join(args))
            continue
        result = subprocess.run(args, cwd=repo_root, text=True,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, check=False)
        if result.stdout:
            logs.append(f"$ {script_name}\n{result.stdout.rstrip()}")
        if result.returncode:
            stop.set()
            raise RuntimeError(
                f"{task.name}: {script_name} exited with {result.returncode}\n" +
                "\n".join(logs))
        print(f"[{task.name}] completed {script_name}", flush=True)
    return task.name, "\n".join(logs)


def run_wave(tasks: tuple[Task, ...], jobs: int, tools_dir: Path,
             output: Path, repo_root: Path, dry_run: bool) -> None:
    stop = threading.Event()
    with ThreadPoolExecutor(max_workers=min(jobs, len(tasks))) as executor:
        futures = {
            executor.submit(run_task, task, tools_dir, output, repo_root,
                            stop, dry_run): task
            for task in tasks
        }
        try:
            for future in as_completed(futures):
                name, logs = future.result()
                if logs:
                    print(f"[{name}] output:\n{logs}", flush=True)
        except Exception:
            stop.set()
            for future in futures:
                future.cancel()
            raise


def run_blocker(task: Task, tools_dir: Path, output: Path,
                repo_root: Path, dry_run: bool) -> None:
    run_task(task, tools_dir, output, repo_root, threading.Event(), dry_run)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", default="build/eloria-data",
                        help="generated data directory (default: build/eloria-data)")
    parser.add_argument("--jobs", "-j", type=int,
                        default=min(8, os.cpu_count() or 1),
                        help="maximum concurrent generator pipelines")
    parser.add_argument("--skip-validation", action="store_true",
                        help="do not run provenance and generated-asset validation")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the dependency schedule without executing it")
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be at least 1")

    tools_dir = Path(__file__).resolve().parent
    repo_root = tools_dir.parents[1]
    output = Path(args.output)
    if not output.is_absolute():
        output = repo_root / output

    run_blocker(Task("bootstrap", ("generate_bootstrap_pack.py",)),
                tools_dir, output, repo_root, args.dry_run)

    print(f"[parallel] starting {len(PARALLEL_WAVE)} pipelines with {args.jobs} workers",
          flush=True)
    run_wave(PARALLEL_WAVE, args.jobs, tools_dir, output, repo_root, args.dry_run)

    # Runtime writes startup-safe stubs that effects intentionally replaces.
    run_blocker(Task("effects", ("generate_effects.py",)), tools_dir,
                output, repo_root, args.dry_run)

    # This consumes the actor registry and all shared generated world assets.
    # Rebuild the portable Four Gates package before merging the Nymara pack.
    # The checked-in runtime copy may be stale or truncated, while the authored
    # GLB and metadata remain the source of truth.
    run_blocker(Task("nymara", ("package_four_gates_world.py",
                                "generate_nymara_complete.py")), tools_dir,
                output, repo_root, args.dry_run)

    if not args.skip_validation:
        run_blocker(Task("validation", ("check_provenance.py",
                                         "validate_generated_assets.py",
                                         "validate_harvestables.py")),
                    tools_dir, output, repo_root, args.dry_run)
    print(f"Complete independent data pack: {output}", flush=True)


if __name__ == "__main__":
    main()
