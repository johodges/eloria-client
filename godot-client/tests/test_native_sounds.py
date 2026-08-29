#!/usr/bin/env python3
"""The generated sound set is original, complete and deterministic.

Every sound the client plays is synthesized by
`eloria-assets/tools/build_native_sounds.py` from noise and sine partials.
This checks the shipped set against that generator: same names, same bytes,
and audio that is actually audio rather than silence.
"""

from __future__ import annotations

import importlib.util
import json
import unittest
import wave
from pathlib import Path

CLIENT_ROOT = Path(__file__).resolve().parents[1]
AUDIO_DIRECTORY = CLIENT_ROOT / "assets" / "audio"
GENERATOR = (CLIENT_ROOT.parent / "eloria-assets" / "tools"
             / "build_native_sounds.py")


def _generator():
    specification = importlib.util.spec_from_file_location(
        "build_native_sounds", GENERATOR)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class NativeSoundTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = _generator()
        cls.catalog = json.loads(
            (AUDIO_DIRECTORY / "catalog.json").read_text(encoding="utf-8"))

    def test_the_catalog_lists_exactly_what_the_generator_makes(self) -> None:
        listed = sorted(sound["name"] for sound in self.catalog["sounds"])
        self.assertEqual(listed, sorted(self.module.RECIPES))

    def test_every_listed_sound_is_present_and_playable(self) -> None:
        for sound in self.catalog["sounds"]:
            path = AUDIO_DIRECTORY / sound["file"]
            with self.subTest(sound=sound["name"]):
                self.assertTrue(path.is_file(), f"{path} is missing")
                with wave.open(str(path), "rb") as handle:
                    self.assertEqual(handle.getnchannels(), 1)
                    self.assertEqual(handle.getsampwidth(), 2)
                    self.assertEqual(handle.getframerate(),
                                     self.catalog["sampleRate"])
                    frames = handle.getnframes()
                self.assertGreater(frames, 1000,
                                   "a sound shorter than this is a click")

    def test_no_sound_is_silence(self) -> None:
        import numpy as np

        for sound in self.catalog["sounds"]:
            with wave.open(str(AUDIO_DIRECTORY / sound["file"]), "rb") as handle:
                samples = np.frombuffer(
                    handle.readframes(handle.getnframes()), dtype="<i2")
            with self.subTest(sound=sound["name"]):
                self.assertGreater(int(np.max(np.abs(samples))), 8000,
                                   "the sound is inaudible")

    def test_rebuilding_produces_the_same_bytes(self) -> None:
        import numpy as np

        for name, recipe in self.module.RECIPES.items():
            samples = recipe()
            peak = float(np.max(np.abs(samples))) or 1.0
            scaled = np.clip(samples / peak * self.module.PEAK, -1.0, 1.0)
            expected = (scaled * 32767.0).astype("<i2").tobytes()
            with wave.open(str(AUDIO_DIRECTORY / f"{name}.wav"), "rb") as handle:
                shipped = handle.readframes(handle.getnframes())
            with self.subTest(sound=name):
                self.assertEqual(shipped, expected,
                                 "the shipped sound is not what the generator"
                                 " produces today")

    def test_the_generator_names_no_external_source(self) -> None:
        source = GENERATOR.read_text(encoding="utf-8").casefold()
        for forbidden in ("freesound", "sample pack", "eternal lands", ".mp3",
                          "download"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
