#!/usr/bin/env python3
"""Validate and summarize Eloria crowd benchmark JSON reports.

The summary deliberately keeps frame percentiles attached to their source run.
Only per-run means are combined across trials, using their median.  This avoids
presenting a percentile computed from samples produced by different processes.
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import hashlib
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any, Iterable


SUMMARY_METRICS = (
    "wallMilliseconds",
    "presentMilliseconds",
    "groundMilliseconds",
    "overheadMilliseconds",
    "animationGateMilliseconds",
    "syncWorldMilliseconds",
    "packetDispatchInclusiveMilliseconds",
    "commandOnlyReduceMilliseconds",
    "rootRenderCpuMilliseconds",
    "rootRenderGpuMilliseconds",
    "worldRenderCpuMilliseconds",
    "worldRenderGpuMilliseconds",
    "drawCalls",
    "primitives",
    "sceneNodes",
    "resourceObjects",
    "transientWorldEffects",
)

PACKET_METRICS = (
    "wallMilliseconds",
    "presentMilliseconds",
    "groundMilliseconds",
    "syncWorldMilliseconds",
    "packetDispatchInclusiveMilliseconds",
    "commandOnlyReduceMilliseconds",
)

HEADLESS_UNAVAILABLE_METRICS = (
    "rootRenderCpuMilliseconds",
    "rootRenderGpuMilliseconds",
    "worldRenderCpuMilliseconds",
    "worldRenderGpuMilliseconds",
    "drawCalls",
    "primitives",
)

ACTIVITY_COLUMNS = (
    ("idle", "Idle"),
    ("all_move", "Move"),
    ("all_combat", "Combat"),
)

SCALING_COUNTS = (100, 200, 300, 500)


class SummaryError(ValueError):
    """Raised when an input is not a trustworthy completed benchmark run."""


def _is_process_metadata(path: Path) -> bool:
    name = path.name.lower()
    return name.endswith(".process.json") or name in {
        "process.json",
        "process-metadata.json",
        "process_metadata.json",
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _finite_number(value: Any, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SummaryError(f"{context} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise SummaryError(f"{context} must be finite")
    return number


def _required_text(mapping: dict[str, Any], key: str, context: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SummaryError(f"{context}.{key} must be a non-empty string")
    return value


def _required_dict(mapping: dict[str, Any], key: str, context: str) -> dict[str, Any]:
    value = mapping.get(key)
    if not isinstance(value, dict):
        raise SummaryError(f"{context}.{key} must be an object")
    return value


def _required_int(mapping: dict[str, Any], key: str, context: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise SummaryError(f"{context}.{key} must be an integer")
    return value


def _required_bool(mapping: dict[str, Any], key: str, context: str) -> bool:
    value = mapping.get(key)
    if not isinstance(value, bool):
        raise SummaryError(f"{context}.{key} must be a boolean")
    return value


def _expected_active_count(count: int, activity: str, context: str) -> int:
    if activity == "idle":
        return 0
    if activity == "move25":
        return count // 4
    if activity in {"third_active", "sync_burst", "asynchronous"}:
        return count // 3
    if activity in {"all_move", "all_combat"}:
        return count
    raise SummaryError(f"{context}.activity has unsupported value {activity!r}")


def _validate_stat(value: Any, context: str, maximum_samples: int) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise SummaryError(f"{context} must be null or an object")
    samples = value.get("samples")
    if isinstance(samples, bool) or not isinstance(samples, int) or samples < 1:
        raise SummaryError(f"{context}.samples must be a positive integer")
    if samples > maximum_samples:
        raise SummaryError(
            f"{context}.samples ({samples}) exceeds the cell frame count ({maximum_samples})"
        )
    checked: dict[str, Any] = {"samples": samples}
    for key in ("mean", "p95", "p99", "max"):
        checked[key] = _finite_number(value.get(key), f"{context}.{key}")
    if checked["p95"] > checked["max"] or checked["p99"] > checked["max"]:
        raise SummaryError(f"{context} percentile exceeds max")
    return checked


def _validate_summary(
    summary: Any,
    context: str,
    frames: int,
    required_metrics: Iterable[str],
) -> dict[str, dict[str, Any] | None]:
    if not isinstance(summary, dict):
        raise SummaryError(f"{context} must be an object")
    result: dict[str, dict[str, Any] | None] = {}
    for metric in set(summary).union(required_metrics):
        result[metric] = _validate_stat(summary.get(metric), f"{context}.{metric}", frames)
    return result


def _validate_cell(cell: Any, run_context: str, min_frames: int, headless: bool) -> dict[str, Any]:
    if not isinstance(cell, dict):
        raise SummaryError(f"{run_context}.cells entries must be objects")
    cell_id = _required_text(cell, "id", run_context)
    context = f"{run_context}.cells[{cell_id}]"
    count = cell.get("count")
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise SummaryError(f"{context}.count must be a positive integer")
    for key in ("activity", "population", "visibility", "features", "network"):
        _required_text(cell, key, context)
    expected_visible = count // 2 if cell["visibility"] in {
        "half300", "frustum_half", "range_bands"
    } else count
    expected_active = _expected_active_count(count, cell["activity"], context)
    fixture = _required_dict(cell, "fixture", context)
    for phase in ("before", "after"):
        census = _required_dict(fixture, phase, f"{context}.fixture")
        actual_total = _required_int(census, "total", f"{context}.fixture.{phase}")
        actual_visible = _required_int(
            census, "frustumAndDrawVisible", f"{context}.fixture.{phase}"
        )
        if actual_total != count:
            raise SummaryError(
                f"{context}.fixture.{phase}.total is {actual_total}; expected {count}"
            )
        if actual_visible != expected_visible:
            raise SummaryError(
                f"{context}.fixture.{phase}.frustumAndDrawVisible is {actual_visible}; "
                f"expected {expected_visible}"
            )
    planned_active = _required_int(cell, "plannedActive", context)
    if planned_active != expected_active:
        raise SummaryError(
            f"{context}.plannedActive is {planned_active}; expected {expected_active} "
            f"for activity {cell['activity']!r}"
        )
    planned_workload = _required_dict(cell, "plannedWorkload", context)
    workload_active = _required_int(planned_workload, "active", f"{context}.plannedWorkload")
    workload_moving = _required_int(planned_workload, "moving", f"{context}.plannedWorkload")
    workload_fighting = _required_int(planned_workload, "fighting", f"{context}.plannedWorkload")
    if workload_active != planned_active or workload_moving + workload_fighting != planned_active:
        raise SummaryError(f"{context}.plannedWorkload does not partition plannedActive")
    if cell["activity"] == "all_combat" and (workload_moving != 0 or workload_fighting != planned_active):
        raise SummaryError(f"{context}.plannedWorkload does not match all_combat")
    if cell["activity"] == "third_active" and (
        workload_moving != planned_active // 2
        or workload_fighting != planned_active - planned_active // 2
    ):
        raise SummaryError(f"{context}.plannedWorkload does not match third_active")
    if cell["activity"] not in {"all_combat", "third_active"} and (
        workload_moving != planned_active or workload_fighting != 0
    ):
        raise SummaryError(f"{context}.plannedWorkload does not match {cell['activity']!r}")
    readiness = _required_dict(cell, "resourceReadiness", context)
    if readiness.get("ready") is not True:
        raise SummaryError(f"{context}.resourceReadiness.ready must be true")
    diagnostics = _required_dict(cell, "diagnostics", context)
    memory = _required_dict(cell, "memory", context)
    spawn = _required_dict(cell, "spawn", context)
    despawn_milliseconds = _finite_number(
        cell.get("despawnMilliseconds"), f"{context}.despawnMilliseconds"
    )
    sample = cell.get("sample")
    if not isinstance(sample, dict):
        raise SummaryError(f"{context}.sample must be an object")
    frames = sample.get("frames")
    if isinstance(frames, bool) or not isinstance(frames, int):
        raise SummaryError(f"{context}.sample.frames must be an integer")
    if frames < min_frames:
        raise SummaryError(
            f"{context}.sample.frames is {frames}; minimum required is {min_frames}"
        )

    summary = _validate_summary(
        sample.get("summary"), f"{context}.sample.summary", frames, SUMMARY_METRICS
    )
    wall = summary.get("wallMilliseconds")
    if wall is None:
        raise SummaryError(f"{context}.sample.summary.wallMilliseconds is unavailable")
    if wall["samples"] != frames:
        raise SummaryError(
            f"{context}.sample.summary.wallMilliseconds.samples must equal frames"
        )

    packet_summary = _validate_summary(
        sample.get("packetBearingSummary", {}),
        f"{context}.sample.packetBearingSummary",
        frames,
        PACKET_METRICS,
    )
    raw = sample.get("raw")
    if not isinstance(raw, dict):
        raise SummaryError(f"{context}.sample.raw must be an object")
    raw_wall = raw.get("wallMilliseconds")
    if not isinstance(raw_wall, list) or len(raw_wall) != frames:
        raise SummaryError(f"{context}.sample.raw.wallMilliseconds length must equal frames")

    if headless:
        for metric in HEADLESS_UNAVAILABLE_METRICS:
            if summary.get(metric) is not None:
                raise SummaryError(
                    f"{context}.sample.summary.{metric} must be null for a headless run"
                )

    rates = sample.get("rates", {})
    if not isinstance(rates, dict):
        raise SummaryError(f"{context}.sample.rates must be an object")
    checked_rates: dict[str, float | None] = {}
    for key, value in rates.items():
        checked_rates[key] = None if value is None else _finite_number(value, f"{context}.sample.rates.{key}")

    return {
        "id": cell_id,
        "count": count,
        "activity": cell["activity"],
        "population": cell["population"],
        "visibility": cell["visibility"],
        "features": cell["features"],
        "network": cell["network"],
        "frames": frames,
        "fixture": fixture,
        "plannedActive": planned_active,
        "plannedWorkload": planned_workload,
        "resourceReadiness": readiness,
        "diagnostics": diagnostics,
        "memory": memory,
        "spawn": spawn,
        "despawnMilliseconds": despawn_milliseconds,
        "summary": summary,
        "packetBearingSummary": packet_summary,
        "rates": checked_rates,
    }


def _planned_id(spec: Any, context: str) -> str:
    if not isinstance(spec, dict):
        raise SummaryError(f"{context} entries must be objects")
    return _required_text(spec, "id", context)


def _validate_run(path: Path, data: Any, min_frames: int) -> dict[str, Any]:
    context = str(path)
    if not isinstance(data, dict):
        raise SummaryError(f"{context}: report root must be an object")
    if data.get("schemaVersion") != 1:
        raise SummaryError(f"{context}: unsupported schemaVersion {data.get('schemaVersion')!r}")
    failure_count = data.get("failureCount")
    if isinstance(failure_count, bool) or not isinstance(failure_count, int):
        raise SummaryError(f"{context}: failureCount must be an integer")
    if failure_count != 0:
        raise SummaryError(f"{context}: failureCount is {failure_count}")
    failures = data.get("failures")
    if not isinstance(failures, list) or failures:
        raise SummaryError(f"{context}: failures must be an empty array")

    run_id = _required_text(data, "runId", context)
    label = _required_text(data, "label", context)
    backend = _required_text(data, "nativeBackend", context)
    renderer = _required_text(data, "actualRenderingMethod", context)
    display = _required_text(data, "display", context)
    commit = _required_text(data, "commit", context)
    source_hash = _required_text(data, "sourceHash", context)
    active = data.get("nativeBackendActive")
    if not isinstance(active, bool):
        raise SummaryError(f"{context}: nativeBackendActive must be a boolean")
    if backend == "native" and not active:
        raise SummaryError(f"{context}: requested native backend was not active")
    if backend == "gdscript" and active:
        raise SummaryError(f"{context}: gdscript backend unexpectedly reports native active")
    if backend not in {"native", "gdscript", "current"}:
        raise SummaryError(f"{context}: unsupported nativeBackend {backend!r}")
    trial = data.get("trial")
    if isinstance(trial, bool) or not isinstance(trial, int) or trial < 1:
        raise SummaryError(f"{context}: trial must be a positive integer")
    headless = data.get("headless")
    if not isinstance(headless, bool):
        raise SummaryError(f"{context}: headless must be a boolean")
    if (display == "headless") != headless:
        raise SummaryError(f"{context}: display/headless fields disagree")
    shared_machine = data.get("sharedMachine")
    if not isinstance(shared_machine, bool):
        raise SummaryError(f"{context}: sharedMachine must be a boolean")

    planned = data.get("plannedCells")
    cells = data.get("cells")
    if not isinstance(planned, list) or not planned:
        raise SummaryError(f"{context}: plannedCells must be a non-empty array")
    if not isinstance(cells, list) or not cells:
        raise SummaryError(f"{context}: cells must be a non-empty array")
    planned_ids = [_planned_id(spec, f"{context}.plannedCells") for spec in planned]
    if len(planned_ids) != len(set(planned_ids)):
        raise SummaryError(f"{context}: plannedCells contains duplicate ids")
    checked_cells = [_validate_cell(cell, context, min_frames, headless) for cell in cells]
    actual_ids = [cell["id"] for cell in checked_cells]
    if len(actual_ids) != len(set(actual_ids)):
        raise SummaryError(f"{context}: cells contains duplicate ids")
    missing = sorted(set(planned_ids) - set(actual_ids))
    extra = sorted(set(actual_ids) - set(planned_ids))
    if missing or extra:
        raise SummaryError(f"{context}: cell plan mismatch; missing={missing}, extra={extra}")
    planned_by_id = {spec["id"]: spec for spec in planned}
    for cell in checked_cells:
        spec = planned_by_id[cell["id"]]
        for key in ("count", "activity", "population", "visibility", "features", "network"):
            if spec.get(key) != cell[key]:
                raise SummaryError(
                    f"{context}: completed cell {cell['id']!r} changed planned {key}; "
                    f"planned={spec.get(key)!r}, actual={cell[key]!r}"
                )

    return {
        "path": str(path.resolve()),
        "sha256": _sha256(path),
        "runId": run_id,
        "label": label,
        "backend": backend,
        "nativeBackendActive": active,
        "renderer": renderer,
        "display": display,
        "headless": headless,
        "commit": commit,
        "sourceHash": source_hash,
        "dirty": data.get("dirty"),
        "trial": trial,
        "sharedMachine": shared_machine,
        "interferenceLabel": data.get("interferenceLabel"),
        "cells": checked_cells,
    }


def _expand_inputs(inputs: list[str], directories: list[str], label: str | None) -> tuple[list[Path], list[Path]]:
    candidates: list[Path] = []
    directory_used = False
    for item in inputs:
        matches = [Path(match) for match in glob.glob(item)]
        if not matches and not glob.has_magic(item):
            matches = [Path(item)]
        for match in matches:
            if match.is_dir():
                directory_used = True
                candidates.extend(match.glob("*.json"))
            else:
                candidates.append(match)
    for item in directories:
        directory_used = True
        directory = Path(item)
        if not directory.is_dir():
            raise SummaryError(f"artifact directory does not exist: {directory}")
        candidates.extend(directory.glob("*.json"))
    if directory_used and not label:
        raise SummaryError("--label is required when reading an artifact directory")

    unique: dict[str, Path] = {}
    ignored: list[Path] = []
    for path in candidates:
        if _is_process_metadata(path):
            ignored.append(path.resolve())
            continue
        if path.suffix.lower() != ".json":
            continue
        if not path.is_file():
            raise SummaryError(f"input file does not exist: {path}")
        unique[str(path.resolve()).lower()] = path.resolve()
    return sorted(unique.values(), key=lambda value: str(value).lower()), sorted(set(ignored))


def _read_runs(paths: list[Path], label: str | None, min_frames: int) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise SummaryError(f"cannot read benchmark JSON {path}: {error}") from error
        if not isinstance(data, dict):
            raise SummaryError(f"{path}: report root must be an object")
        if label is not None and data.get("label") != label:
            continue
        runs.append(_validate_run(path, data, min_frames))
    if not runs:
        suffix = f" for label {label!r}" if label else ""
        raise SummaryError(f"no benchmark runs selected{suffix}")
    run_ids = [run["runId"] for run in runs]
    if len(run_ids) != len(set(run_ids)):
        raise SummaryError("selected inputs contain duplicate runId values")
    return runs


def _validate_companion(run: dict[str, Any], allow_missing_for_fixtures: bool) -> None:
    report_path = Path(run["path"])
    companion_path = report_path.with_name(report_path.stem + ".process.json")
    context = str(companion_path)
    if not companion_path.is_file():
        if not allow_missing_for_fixtures:
            raise SummaryError(
                f"{report_path}: required process companion is missing: {companion_path}; "
                "use --allow-missing-process-companion-for-fixtures only for independent fixtures"
            )
        run["companionProcess"] = {
            "status": "missingFixtureOptOut",
            "path": str(companion_path.resolve()),
            "sha256": None,
            "fixtureOptOut": True,
            "executableIdentityAvailable": False,
        }
        return
    try:
        data = json.loads(companion_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SummaryError(f"cannot read process companion {companion_path}: {error}") from error
    if not isinstance(data, dict):
        raise SummaryError(f"{context}: process companion root must be an object")

    expected_fields = {
        "runId": run["runId"],
        "backend": run["backend"],
        "renderer": run["renderer"],
        "mode": "headless" if run["headless"] else "windowed",
        "trial": run["trial"],
        "commit": run["commit"],
        "sourceHash": run["sourceHash"],
    }
    for key, expected in expected_fields.items():
        if data.get(key) != expected:
            raise SummaryError(
                f"{context}.{key} does not match its report; "
                f"companion={data.get(key)!r}, report={expected!r}"
            )
    exit_code = _required_int(data, "exitCode", context)
    if exit_code != 0:
        raise SummaryError(f"{context}.exitCode is {exit_code}; expected 0")
    if not _required_bool(data, "cleanExit", context):
        raise SummaryError(f"{context}.cleanExit is false")
    if _required_bool(data, "abortedAfterReport", context):
        raise SummaryError(f"{context}.abortedAfterReport is true")
    if _required_bool(data, "postReportStop", context):
        raise SummaryError(f"{context}.postReportStop is true (forced post-report termination)")
    for key in ("forcedTermination", "forceTerminated"):
        if key in data and _required_bool(data, key, context):
            raise SummaryError(f"{context}.{key} is true")
    if "reportValid" in data and not _required_bool(data, "reportValid", context):
        raise SummaryError(f"{context}.reportValid is false")
    if "schemaValid" in data and not _required_bool(data, "schemaValid", context):
        raise SummaryError(f"{context}.schemaValid is false")
    if "scriptErrorsDetected" in data and _required_bool(data, "scriptErrorsDetected", context):
        raise SummaryError(f"{context}.scriptErrorsDetected is true")
    current_attestation = any(
        key in data for key in ("reportValid", "schemaValid", "scriptErrorsDetected")
    )
    if current_attestation:
        for key in ("reportValid", "scriptErrorsDetected"):
            if key not in data:
                raise SummaryError(f"{context}.{key} is required for current process metadata")

    affinity_mask = _required_int(data, "affinityMask", context)
    if affinity_mask != 0xF:
        raise SummaryError(f"{context}.affinityMask is {affinity_mask}; expected 15")
    if not _required_bool(data, "allObservedProcessesVerified", context):
        raise SummaryError(f"{context}.allObservedProcessesVerified is false")
    observed = _required_dict(data, "observedProcesses", context)
    if not observed:
        raise SummaryError(f"{context}.observedProcesses must not be empty")
    root_pid = _required_int(data, "rootPid", context)
    if str(root_pid) not in observed:
        raise SummaryError(f"{context}.rootPid is absent from observedProcesses")
    identity_available = True
    for pid, raw_process in observed.items():
        if not isinstance(raw_process, dict):
            raise SummaryError(f"{context}.observedProcesses[{pid!r}] must be an object")
        mask = _required_int(raw_process, "affinityMask", f"{context}.observedProcesses[{pid!r}]")
        if mask <= 0 or mask & ~0xF:
            raise SummaryError(
                f"{context}.observedProcesses[{pid!r}].affinityMask ({mask}) "
                "uses CPUs outside mask 15"
            )
        if not isinstance(raw_process.get("name"), str) or not raw_process["name"]:
            raise SummaryError(f"{context}.observedProcesses[{pid!r}].name is missing")
        if not isinstance(raw_process.get("path"), str) or not raw_process["path"]:
            identity_available = False
        if not isinstance(raw_process.get("startTimeUtc"), str) or not raw_process["startTimeUtc"]:
            identity_available = False

    requested_path = data.get("requestedGodotPath")
    launch_path = data.get("launchExecutablePath")
    if current_attestation:
        if not isinstance(requested_path, str) or not requested_path:
            raise SummaryError(f"{context}.requestedGodotPath is required for current metadata")
        if not isinstance(launch_path, str) or not launch_path:
            raise SummaryError(f"{context}.launchExecutablePath is required for current metadata")
        if not identity_available:
            raise SummaryError(f"{context}: current metadata lacks process path/start identity")
        normalized_launch = launch_path.replace("/", "\\").lower()
        for pid, raw_process in observed.items():
            normalized_observed = raw_process["path"].replace("/", "\\").lower()
            if normalized_observed != normalized_launch:
                raise SummaryError(
                    f"{context}.observedProcesses[{pid!r}].path does not match launchExecutablePath"
                )

    source_files = _required_dict(data, "sourceFiles", context)
    if not source_files:
        raise SummaryError(f"{context}.sourceFiles must not be empty")
    for source_path, digest in source_files.items():
        if not isinstance(source_path, str) or not source_path or not isinstance(digest, str) or not digest:
            raise SummaryError(f"{context}.sourceFiles must map non-empty paths to hashes")
    dirty = data.get("dirty")
    if not isinstance(dirty, bool):
        raise SummaryError(f"{context}.dirty must be a boolean")

    run["companionProcess"] = {
        "status": "validated",
        "metadataGeneration": "current" if current_attestation else "legacy",
        "path": str(companion_path.resolve()),
        "sha256": _sha256(companion_path),
        "fixtureOptOut": False,
        "runId": data["runId"],
        "rootPid": root_pid,
        "exitCode": exit_code,
        "cleanExit": data["cleanExit"],
        "abortedAfterReport": data["abortedAfterReport"],
        "postReportStop": data["postReportStop"],
        "reportValid": data.get("reportValid"),
        "schemaValid": data.get("schemaValid"),
        "scriptErrorsDetected": data.get("scriptErrorsDetected"),
        "affinityMask": affinity_mask,
        "allObservedProcessesVerified": data["allObservedProcessesVerified"],
        "observedProcesses": observed,
        "executableIdentityAvailable": identity_available,
        "requestedGodotPath": requested_path,
        "launchExecutablePath": launch_path,
        "commit": data["commit"],
        "dirty": dirty,
        "sourceHash": data["sourceHash"],
        "sourceFiles": source_files,
        "monitoring": data.get("monitoring"),
    }


def _aggregate_metric(
    cell_runs: list[tuple[dict[str, Any], dict[str, Any]]], section: str, metric: str
) -> dict[str, Any]:
    per_run: list[dict[str, Any]] = []
    means: list[float] = []
    unavailable = 0
    for run, cell in cell_runs:
        stat = cell[section].get(metric)
        entry = {"runId": run["runId"], "trial": run["trial"]}
        if stat is None:
            entry["value"] = None
            unavailable += 1
        else:
            value = {
                "samples": stat["samples"],
                "mean": stat["mean"],
                "p95": stat["p95"],
                "p99": stat["p99"],
                "max": stat["max"],
            }
            entry["value"] = value
            means.append(stat["mean"])
        per_run.append(entry)
    return {
        "medianOfRunMeans": statistics.median(means) if means else None,
        "availableRuns": len(means),
        "unavailableRuns": unavailable,
        "perRun": per_run,
    }


def _aggregate_rate(
    cell_runs: list[tuple[dict[str, Any], dict[str, Any]]], metric: str
) -> dict[str, Any]:
    per_run: list[dict[str, Any]] = []
    values: list[float] = []
    for run, cell in cell_runs:
        value = cell["rates"].get(metric)
        per_run.append({"runId": run["runId"], "trial": run["trial"], "value": value})
        if value is not None:
            values.append(value)
    return {
        "medianOfRunValues": statistics.median(values) if values else None,
        "availableRuns": len(values),
        "unavailableRuns": len(per_run) - len(values),
        "perRun": per_run,
    }


def _aggregate_cell(cell_runs: list[tuple[dict[str, Any], dict[str, Any]]]) -> dict[str, Any]:
    first = cell_runs[0][1]
    invariant_keys = ("count", "activity", "population", "visibility", "features", "network")
    for _, cell in cell_runs[1:]:
        for key in invariant_keys:
            if cell[key] != first[key]:
                raise SummaryError(
                    f"cell {first['id']!r} has inconsistent {key}: "
                    f"{first[key]!r} versus {cell[key]!r}"
                )
    seen_trials: set[int] = set()
    for run, _ in cell_runs:
        if run["trial"] in seen_trials:
            raise SummaryError(
                f"cell {first['id']!r} has duplicate trial number {run['trial']} in one group"
            )
        seen_trials.add(run["trial"])

    summary_names = sorted(set(SUMMARY_METRICS).union(*(cell["summary"] for _, cell in cell_runs)))
    packet_names = sorted(set(PACKET_METRICS).union(*(cell["packetBearingSummary"] for _, cell in cell_runs)))
    rate_names = sorted(set().union(*(cell["rates"] for _, cell in cell_runs)))
    result = {key: first[key] for key in ("id", *invariant_keys)}
    result.update(
        {
            "trialCount": len(cell_runs),
            "minimumFramesObserved": min(cell["frames"] for _, cell in cell_runs),
            "framesPerRun": [
                {"runId": run["runId"], "trial": run["trial"], "frames": cell["frames"]}
                for run, cell in cell_runs
            ],
            "evidencePerRun": [
                {
                    "runId": run["runId"],
                    "trial": run["trial"],
                    "fixture": cell["fixture"],
                    "plannedActive": cell["plannedActive"],
                    "plannedWorkload": cell["plannedWorkload"],
                    "resourceReadiness": cell["resourceReadiness"],
                    "diagnostics": cell["diagnostics"],
                    "memory": cell["memory"],
                    "spawn": cell["spawn"],
                    "despawnMilliseconds": cell["despawnMilliseconds"],
                }
                for run, cell in cell_runs
            ],
            "metrics": {
                metric: _aggregate_metric(cell_runs, "summary", metric)
                for metric in summary_names
            },
            "packetBearingMetrics": {
                metric: _aggregate_metric(cell_runs, "packetBearingSummary", metric)
                for metric in packet_names
            },
            "rates": {metric: _aggregate_rate(cell_runs, metric) for metric in rate_names},
        }
    )
    return result


def _aggregate(runs: list[dict[str, Any]], min_frames: int, ignored: list[Path]) -> dict[str, Any]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for run in runs:
        groups.setdefault((run["backend"], run["renderer"], run["display"]), []).append(run)

    group_results: list[dict[str, Any]] = []
    for key in sorted(groups):
        group_runs = sorted(groups[key], key=lambda run: (run["trial"], run["runId"]))
        commits = {run["commit"] for run in group_runs}
        source_hashes = {run["sourceHash"] for run in group_runs}
        labels = {run["label"] for run in group_runs}
        active_values = {run["nativeBackendActive"] for run in group_runs}
        headless_values = {run["headless"] for run in group_runs}
        if len(commits) != 1 or len(source_hashes) != 1:
            raise SummaryError(
                f"group {key} mixes commit/sourceHash provenance; summarize those runs separately"
            )
        if len(labels) != 1:
            raise SummaryError(f"group {key} mixes benchmark labels; select one with --label")
        if len(active_values) != 1 or len(headless_values) != 1:
            raise SummaryError(f"group {key} mixes backend-active or headless state")
        expected_cells = {cell["id"] for cell in group_runs[0]["cells"]}
        for run in group_runs[1:]:
            actual_cells = {cell["id"] for cell in run["cells"]}
            if actual_cells != expected_cells:
                raise SummaryError(
                    f"group {key} run {run['runId']!r} has a different cell set; "
                    f"missing={sorted(expected_cells - actual_cells)}, "
                    f"extra={sorted(actual_cells - expected_cells)}"
                )

        by_cell: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
        for run in group_runs:
            for cell in run["cells"]:
                by_cell.setdefault(cell["id"], []).append((run, cell))
        cells = [_aggregate_cell(by_cell[cell_id]) for cell_id in sorted(by_cell)]
        shared = any(run["sharedMachine"] for run in group_runs)
        interference = sorted(
            {
                str(run["interferenceLabel"])
                for run in group_runs
                if run["interferenceLabel"] not in (None, "")
            }
        )
        caveats = []
        if shared:
            caveats.append(
                "Runs were collected on a shared host; scheduler and concurrent-load noise may affect comparisons."
            )
        if key[2] == "headless":
            caveats.append(
                "Headless renderer, GPU, draw-call, and primitive metrics are unavailable and remain null."
            )
        group_results.append(
            {
                "backend": key[0],
                "nativeBackendActive": next(iter(active_values)),
                "renderer": key[1],
                "display": key[2],
                "label": next(iter(labels)),
                "headless": next(iter(headless_values)),
                "commit": next(iter(commits)),
                "sourceHash": next(iter(source_hashes)),
                "dirtyValues": sorted({str(run["dirty"]) for run in group_runs}),
                "sharedMachine": shared,
                "interferenceLabels": interference,
                "caveats": caveats,
                "runCount": len(group_runs),
                "runs": [
                    {
                        "runId": run["runId"],
                        "trial": run["trial"],
                        "label": run["label"],
                        "path": run["path"],
                        "sha256": run["sha256"],
                        "companionProcess": run["companionProcess"],
                    }
                    for run in group_runs
                ],
                "cells": cells,
            }
        )

    companions = [run["companionProcess"] for run in runs]
    validated_companions = [item for item in companions if item["status"] == "validated"]
    fixture_opt_outs = [item for item in companions if item["status"] == "missingFixtureOptOut"]
    selected_companion_paths = {
        str(Path(item["path"])).lower() for item in validated_companions
    }

    return {
        "schemaVersion": 1,
        "generatedAtUtc": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "aggregationMethod": (
            "median of per-run means; per-run p95, p99, and max retained; "
            "percentiles are not pooled across processes"
        ),
        "minimumFrameRequirement": min_frames,
        "inputs": {
            "files": [
                {"path": run["path"], "sha256": run["sha256"]}
                for run in sorted(runs, key=lambda item: item["path"].lower())
            ],
            "companionProcessMetadata": {
                "aggregationUse": "validationOnlyExcludedFromTimingAggregation",
                "validationStatus": "fixtureOptOutPresent" if fixture_opt_outs else "validated",
                "files": [
                    {
                        "path": item["path"],
                        "sha256": item["sha256"],
                        "metadataGeneration": item["metadataGeneration"],
                        "executableIdentityAvailable": item["executableIdentityAvailable"],
                    }
                    for item in validated_companions
                ],
                "fixtureOptOuts": fixture_opt_outs,
                "unmatchedExcludedCandidateCount": sum(
                    1 for path in ignored if str(path).lower() not in selected_companion_paths
                ),
            },
        },
        "groups": group_results,
    }


def _format_number(value: Any) -> str:
    if value is None:
        return "—"
    return f"{float(value):.3f}"


def _run_values(metric: dict[str, Any], key: str) -> str:
    values = [entry["value"].get(key) for entry in metric["perRun"] if entry["value"] is not None]
    return ", ".join(_format_number(value) for value in values) if values else "—"


def _find_scaling_cell(cells: list[dict[str, Any]], count: int, activity: str) -> dict[str, Any] | None:
    matches = [cell for cell in cells if cell["count"] == count and cell["activity"] == activity]
    if not matches:
        return None
    preferred = [cell for cell in matches if cell["id"] == f"matrix-{count}-{activity}"]
    if len(preferred) == 1:
        return preferred[0]
    if len(matches) == 1:
        return matches[0]
    raise SummaryError(f"multiple cells match scaling row count={count}, activity={activity}")


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Crowd benchmark summary",
        "",
        "Values labeled `median of run means` combine trial means only. Per-run p95, p99, and max values remain attached to their source process; this report does not pool percentiles.",
        "",
        f"Minimum accepted frame count per cell: **{report['minimumFrameRequirement']}**.",
        "",
    ]
    for group in report["groups"]:
        lines.extend(
            [
                f"## {group['backend']} · {group['renderer']} · {group['display']}",
                "",
                f"Commit: `{group['commit']}`  ",
                f"Source hash: `{group['sourceHash']}`  ",
                f"Runs: {group['runCount']}",
                "",
            ]
        )
        for caveat in group["caveats"]:
            lines.append(f"- {caveat}")
        if group["interferenceLabels"]:
            lines.append("- Interference labels: " + ", ".join(group["interferenceLabels"]))
        if group["caveats"] or group["interferenceLabels"]:
            lines.append("")

        lines.extend(
            [
                "### Scaling: wall milliseconds, median of run means",
                "",
                "| Actors | Idle | Move | Combat |",
                "| ---: | ---: | ---: | ---: |",
            ]
        )
        for count in SCALING_COUNTS:
            row = [str(count)]
            for activity, _ in ACTIVITY_COLUMNS:
                cell = _find_scaling_cell(group["cells"], count, activity)
                value = None if cell is None else cell["metrics"]["wallMilliseconds"]["medianOfRunMeans"]
                row.append(_format_number(value))
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")

        primary = next((cell for cell in group["cells"] if cell["id"] == "acceptance-mixed300"), None)
        lines.extend(
            [
                "### Primary cell components",
                "",
                "All-frame component values are milliseconds.",
                "",
                "| Component | Median of run means | Per-run means | Per-run p95 | Per-run p99 | Per-run max |",
                "| --- | ---: | --- | --- | --- | --- |",
            ]
        )
        for metric in (
            "wallMilliseconds",
            "presentMilliseconds",
            "groundMilliseconds",
            "overheadMilliseconds",
            "animationGateMilliseconds",
            "syncWorldMilliseconds",
            "packetDispatchInclusiveMilliseconds",
            "commandOnlyReduceMilliseconds",
        ):
            aggregate = None if primary is None else primary["metrics"].get(metric)
            if aggregate is None:
                cells = [metric, "—", "—", "—", "—", "—"]
            else:
                cells = [
                    metric,
                    _format_number(aggregate["medianOfRunMeans"]),
                    _run_values(aggregate, "mean"),
                    _run_values(aggregate, "p95"),
                    _run_values(aggregate, "p99"),
                    _run_values(aggregate, "max"),
                ]
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")

        lines.extend(
            [
                "Packet-bearing frames are summarized separately; their sample counts can be lower than the cell frame count.",
                "",
                "| Packet-bearing component | Median of run means | Per-run means | Per-run p95 | Per-run p99 | Per-run max |",
                "| --- | ---: | --- | --- | --- | --- |",
            ]
        )
        for metric in PACKET_METRICS:
            aggregate = None if primary is None else primary["packetBearingMetrics"].get(metric)
            if aggregate is None:
                cells = [metric, "—", "—", "—", "—", "—"]
            else:
                cells = [
                    metric,
                    _format_number(aggregate["medianOfRunMeans"]),
                    _run_values(aggregate, "mean"),
                    _run_values(aggregate, "p95"),
                    _run_values(aggregate, "p99"),
                    _run_values(aggregate, "max"),
                ]
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")

    lines.extend(["## Inputs", ""])
    for item in report["inputs"]["files"]:
        lines.append(f"- `{item['sha256']}`  `{item['path']}`")
    process_metadata = report["inputs"]["companionProcessMetadata"]
    lines.extend(["", "Companion process metadata is excluded from timing aggregation and validated as a report gate."])
    for item in process_metadata["files"]:
        identity = "identity recorded" if item["executableIdentityAvailable"] else "legacy: executable identity unavailable"
        lines.append(f"- `{item['sha256']}`  `{item['path']}` ({identity})")
    for item in process_metadata["fixtureOptOuts"]:
        lines.append(f"- Fixture opt-out: missing companion `{item['path']}`")
    lines.append("")
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "inputs",
        nargs="*",
        help="Explicit benchmark JSON paths, globs, or directories. Quote globs on Windows.",
    )
    parser.add_argument(
        "--artifact-directory",
        action="append",
        default=[],
        metavar="DIR",
        help="Directory containing run JSON files; requires --label. May be repeated.",
    )
    parser.add_argument("--label", help="Select only reports whose label exactly matches this value.")
    parser.add_argument(
        "--min-frames",
        type=int,
        default=60,
        help="Reject any completed cell with fewer frames (default: 60).",
    )
    parser.add_argument(
        "--json-output",
        default="crowd-benchmark-summary.json",
        metavar="PATH",
        help="Compact machine-readable output path.",
    )
    parser.add_argument(
        "--markdown-output",
        default="crowd-benchmark-summary.md",
        metavar="PATH",
        help="Markdown table output path.",
    )
    parser.add_argument(
        "--allow-missing-process-companion-for-fixtures",
        action="store_true",
        help=(
            "Allow a missing .process.json only for independently constructed parser fixtures. "
            "Existing companions are always validated and benchmark reports should not use this opt-out."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.min_frames < 1:
            raise SummaryError("--min-frames must be positive")
        if not args.inputs and not args.artifact_directory:
            raise SummaryError("provide at least one JSON path, glob, or artifact directory")
        paths, ignored = _expand_inputs(args.inputs, args.artifact_directory, args.label)
        runs = _read_runs(paths, args.label, args.min_frames)
        for run in runs:
            _validate_companion(run, args.allow_missing_process_companion_for_fixtures)
        report = _aggregate(runs, args.min_frames, ignored)
        json_output = Path(args.json_output)
        markdown_output = Path(args.markdown_output)
        json_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(
            json.dumps(report, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        markdown_output.write_text(_markdown(report), encoding="utf-8")
    except (OSError, SummaryError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(
        f"summarized {len(report['inputs']['files'])} run(s) into "
        f"{json_output} and {markdown_output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
