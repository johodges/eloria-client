"""Regression tests for crowd benchmark evidence validation."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


CLIENT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = CLIENT_ROOT / "scripts" / "summarize_crowd_benchmarks.py"
SPEC = importlib.util.spec_from_file_location("summarize_crowd_benchmarks", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
SUMMARY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SUMMARY)


def _distribution(samples: int, mean: float, p50: float, p95: float,
                  p99: float, maximum: float) -> dict[str, float | int]:
    return {
        "samples": samples,
        "mean": mean,
        "p50": p50,
        "p95": p95,
        "p99": p99,
        "max": maximum,
    }


def _raw_fixture() -> tuple[dict, dict, dict]:
    values = [float(value) for value in range(1, 101)]
    value_distribution = _distribution(100, 50.5, 50.0, 95.0, 99.0, 100.0)
    raw = {metric: values.copy() for metric in SUMMARY.PACKET_METRICS}
    raw["packetsPerFrame"] = [1.0] * 100
    summary = {
        metric: copy.deepcopy(value_distribution) for metric in SUMMARY.PACKET_METRICS
    }
    summary["packetsPerFrame"] = _distribution(100, 1.0, 1.0, 1.0, 1.0, 1.0)
    packet_summary = {
        metric: copy.deepcopy(value_distribution) for metric in SUMMARY.PACKET_METRICS
    }
    return raw, summary, packet_summary


def _validate_raw(raw: dict, summary: dict, packet_summary: dict) -> None:
    SUMMARY._validate_raw_distributions(
        raw,
        summary,
        summary,
        packet_summary,
        packet_summary,
        100,
        "sample",
    )


def _run(report_path: Path, *, dirty: bool = False) -> dict:
    report_path.write_text("{}", encoding="utf-8")
    return {
        "path": str(report_path),
        "runId": "synthetic-run",
        "backend": "gdscript",
        "renderer": "forward_plus",
        "headless": False,
        "trial": 1,
        "commit": "0123456789abcdef",
        "sourceHash": "source-hash",
        "dirty": dirty,
    }


def _companion(*, dirty: bool = False) -> dict:
    return {
        "runId": "synthetic-run",
        "backend": "gdscript",
        "renderer": "forward_plus",
        "mode": "windowed",
        "trial": 1,
        "commit": "0123456789abcdef",
        "sourceHash": "source-hash",
        "exitCode": 0,
        "cleanExit": True,
        "abortedAfterReport": False,
        "postReportStop": False,
        "reportValid": True,
        "schemaValid": True,
        "scriptErrorsDetected": False,
        "forcedTermination": False,
        "monitoringError": "",
        "affinityMask": 15,
        "allObservedProcessesVerified": True,
        "rootPid": 123,
        "observedProcesses": {
            "123": {
                "affinityMask": 15,
                "name": "Godot",
                "path": "C:/Godot/Godot.exe",
                "startTimeUtc": "2026-09-19T10:00:00Z",
            }
        },
        "requestedGodotPath": "C:/Godot/Godot.exe",
        "launchExecutablePath": "C:/Godot/Godot.exe",
        "sourceFiles": {"godot-client/source.gd": "digest"},
        "dirty": dirty,
        "monitoring": "synthetic exact-process monitor",
    }


class RawDistributionValidationTests(unittest.TestCase):
    def test_rejects_mean_that_does_not_match_raw_samples(self) -> None:
        raw, summary, packet_summary = _raw_fixture()
        summary["wallMilliseconds"]["mean"] = 50.6

        with self.assertRaisesRegex(SUMMARY.SummaryError, r"wallMilliseconds\.mean"):
            _validate_raw(raw, summary, packet_summary)

    def test_rejects_tail_that_does_not_match_raw_samples(self) -> None:
        raw, summary, packet_summary = _raw_fixture()
        summary["wallMilliseconds"]["p99"] = 98.0

        with self.assertRaisesRegex(SUMMARY.SummaryError, r"wallMilliseconds\.p99"):
            _validate_raw(raw, summary, packet_summary)

    def test_rejects_non_finite_raw_sample(self) -> None:
        raw, summary, packet_summary = _raw_fixture()
        raw["wallMilliseconds"][50] = float("inf")

        with self.assertRaisesRegex(SUMMARY.SummaryError, r"raw\.wallMilliseconds\[50\].*finite"):
            _validate_raw(raw, summary, packet_summary)


class CompanionValidationTests(unittest.TestCase):
    def _validate(self, companion: dict, *, report_dirty: bool = False) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "run.json"
            run = _run(report_path, dirty=report_dirty)
            companion_path = report_path.with_name("run.process.json")
            companion_path.write_text(json.dumps(companion), encoding="utf-8")
            SUMMARY._validate_companion(run, allow_missing_for_fixtures=False)

    def test_accepts_complete_current_attestation(self) -> None:
        self._validate(_companion())

    def test_rejects_nonempty_monitoring_error(self) -> None:
        companion = _companion()
        companion["monitoringError"] = "process identity probe failed"

        with self.assertRaisesRegex(SUMMARY.SummaryError, "monitoringError is non-empty"):
            self._validate(companion)

    def test_current_attestation_flags_are_all_required(self) -> None:
        for field in (
            "reportValid",
            "schemaValid",
            "scriptErrorsDetected",
            "forcedTermination",
            "monitoringError",
        ):
            with self.subTest(field=field):
                companion = _companion()
                del companion[field]
                with self.assertRaisesRegex(SUMMARY.SummaryError, rf"\.{field} is required"):
                    self._validate(companion)

    def test_rejects_dirty_state_mismatch(self) -> None:
        with self.assertRaisesRegex(SUMMARY.SummaryError, "dirty does not match its report"):
            self._validate(_companion(dirty=True), report_dirty=False)


class LodFixtureValidationTests(unittest.TestCase):
    @staticmethod
    def _fixture() -> dict:
        return {
            "before": {
                "distanceBands": {
                    "near0To45": 100,
                    "mid45To80": 100,
                    "beyond80": 100,
                },
                "animationTiers": {"full": 100, "half": 100, "paused": 100},
                "frustumAndDrawVisible": 200,
                "frustumIntersecting": 200,
                "withinDrawDistance": 200,
            },
            "after": {
                "animationTiers": {"full": 101, "half": 99, "paused": 100},
            },
            "camera": {
                "distance": 32.0,
                "pitchDegrees": -25.0,
                "yawDegrees": 0.0,
                "fieldOfViewDegrees": 50.0,
            },
            "visibilityValidation": {"min": 200, "max": 200},
            "grounding": {"surfaceHits": 300, "surfaceMatches": 300, "surfaceMisses": 0},
        }

    def test_accepts_declared_lod_census_and_post_workload_one_shot_shift(self) -> None:
        self.assertEqual(SUMMARY._expected_visible_count(300, "lod_bands", "cell"), 200)
        SUMMARY._validate_lod_fixture(self._fixture(), 300, "cell.fixture")

    def test_rejects_wrong_initial_band_or_tier(self) -> None:
        corruptions = (
            ("distanceBands", "mid45To80", 99),
            ("animationTiers", "half", 99),
        )
        for group, key, value in corruptions:
            with self.subTest(group=group, key=key):
                fixture = self._fixture()
                fixture["before"][group][key] = value
                with self.assertRaisesRegex(SUMMARY.SummaryError, rf"before\.{group}"):
                    SUMMARY._validate_lod_fixture(fixture, 300, "cell.fixture")


class MarkdownRegressionTests(unittest.TestCase):
    @staticmethod
    def _metric(value: float | None) -> dict:
        per_run = [] if value is None else [{
            "runId": "synthetic-run",
            "trial": 1,
            "value": {"mean": value, "p95": value, "p99": value, "max": value},
        }]
        return {"medianOfRunMeans": value, "perRun": per_run}

    def test_ambiguous_feature_cells_stay_out_of_scaling_projection(self) -> None:
        cells = []
        for feature, value in (("full", 10.0), ("no_cape", 8.0)):
            cells.append({
                "id": f"features-300-{feature}",
                "count": 300,
                "activity": "third_active",
                "metrics": {
                    "wallMilliseconds": self._metric(value),
                    "worldRenderCpuMilliseconds": self._metric(None),
                    "worldRenderGpuMilliseconds": self._metric(None),
                    "drawCalls": self._metric(None),
                },
            })
        report = {
            "minimumFrameRequirement": 60,
            "groups": [{
                "backend": "gdscript",
                "renderer": "dummy",
                "display": "headless",
                "headless": True,
                "commit": "0123456789abcdef",
                "sourceHash": "source-hash",
                "runCount": 1,
                "driver": {"productionFaithful": True, "version": SUMMARY.DRIVER_VERSION},
                "caveats": [],
                "interferenceLabels": [],
                "cells": cells,
            }],
            "inputs": {
                "files": [],
                "companionProcessMetadata": {"files": [], "fixtureOptOuts": []},
            },
        }

        markdown = SUMMARY._markdown(report)

        self.assertNotIn("### Scaling:", markdown)
        self.assertIn("`features-300-full`", markdown)
        self.assertIn("`features-300-no_cape`", markdown)


if __name__ == "__main__":
    unittest.main()
