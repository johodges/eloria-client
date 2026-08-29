#!/usr/bin/env python3
"""Synthesize Eloria's original sound set.

Every sound here is generated from first principles - noise, sine partials and
envelopes - so nothing is sampled, converted or traced from another game. The
output is 16-bit mono PCM WAV at 44.1 kHz, which Godot imports without any
plugin.

The generator is deterministic: a fixed seed per sound means rebuilding
produces the same bytes, so a rebuild is a no-op in review unless a recipe
actually changed.

Usage:
    python tools/build_native_sounds.py [--out ../godot-client/assets/audio]
"""

from __future__ import annotations

import argparse
import json
import struct
import wave
from pathlib import Path

import numpy as np

SAMPLE_RATE = 44_100
PEAK = 0.82


def envelope(length: int, attack: float, decay: float, sustain: float = 0.0,
             release: float = 0.0) -> np.ndarray:
    """A four-stage amplitude envelope over `length` samples, in seconds."""
    stages = []
    for seconds, start, end in (
            (attack, 0.0, 1.0), (decay, 1.0, sustain if sustain else 0.0),
            (release, sustain if sustain else 0.0, 0.0)):
        count = max(0, int(seconds * SAMPLE_RATE))
        if count:
            stages.append(np.linspace(start, end, count, endpoint=False))
    curve = np.concatenate(stages) if stages else np.zeros(0)
    if curve.size >= length:
        return curve[:length]
    return np.concatenate([curve, np.zeros(length - curve.size)])


def tone(frequency: float, length: int, partials=(1.0,), detune: float = 0.0,
         seed: int = 0) -> np.ndarray:
    """A harmonic stack, optionally detuned by a slow random wander."""
    time = np.arange(length) / SAMPLE_RATE
    wander = 0.0
    if detune:
        generator = np.random.default_rng(seed)
        wander = np.cumsum(generator.normal(0.0, detune, length)) / SAMPLE_RATE
    wave_form = np.zeros(length)
    for index, weight in enumerate(partials, start=1):
        wave_form += weight * np.sin(
            2.0 * np.pi * frequency * index * (time + wander))
    return wave_form / max(1.0, sum(partials))


def noise(length: int, seed: int, smoothing: int = 1) -> np.ndarray:
    generator = np.random.default_rng(seed)
    raw = generator.uniform(-1.0, 1.0, length + smoothing)
    if smoothing > 1:
        window = np.ones(smoothing) / smoothing
        raw = np.convolve(raw, window, mode="valid")
    return raw[:length]


def seconds(value: float) -> int:
    return int(value * SAMPLE_RATE)


# --- the recipes --------------------------------------------------------------
#
# Each returns a float array in -1..1. The names describe what the sound is
# for, not what it imitates: these are Eloria's sounds, generated here.

def ui_click() -> np.ndarray:
    length = seconds(0.09)
    body = tone(880.0, length, (1.0, 0.35, 0.12))
    return body * envelope(length, 0.002, 0.088)


def ui_close() -> np.ndarray:
    length = seconds(0.14)
    body = tone(440.0, length, (1.0, 0.28)) * 0.9
    return body * envelope(length, 0.004, 0.136)


def harvest_start() -> np.ndarray:
    length = seconds(0.42)
    rustle = noise(length, seed=11, smoothing=48) * 0.55
    lift = tone(320.0, length, (1.0, 0.4, 0.18), detune=6.0, seed=12) * 0.45
    return (rustle + lift) * envelope(length, 0.03, 0.2, 0.35, 0.19)


def harvest_gather() -> np.ndarray:
    length = seconds(0.22)
    grain = noise(length, seed=21, smoothing=16) * 0.6
    click = tone(620.0, length, (1.0, 0.5)) * 0.4
    return (grain + click) * envelope(length, 0.004, 0.216)


def item_pickup() -> np.ndarray:
    length = seconds(0.3)
    first = tone(660.0, length, (1.0, 0.3)) * envelope(length, 0.005, 0.12)
    second = tone(990.0, length, (1.0, 0.25))
    second_envelope = np.concatenate(
        [np.zeros(seconds(0.09)), envelope(length - seconds(0.09), 0.004, 0.2)])
    return first * 0.7 + second * second_envelope * 0.6


def combat_hit() -> np.ndarray:
    length = seconds(0.26)
    impact = noise(length, seed=31, smoothing=6) * 0.8
    body = tone(140.0, length, (1.0, 0.6, 0.3)) * 0.6
    return (impact + body) * envelope(length, 0.002, 0.1, 0.28, 0.15)


def combat_miss() -> np.ndarray:
    length = seconds(0.24)
    swish = noise(length, seed=41, smoothing=96) * 0.9
    sweep = np.linspace(0.2, 1.0, length) ** 2
    return swish * sweep * envelope(length, 0.05, 0.19)


def spell_cast() -> np.ndarray:
    length = seconds(0.75)
    shimmer = np.zeros(length)
    for index, frequency in enumerate((523.25, 659.25, 783.99, 1046.5)):
        start = seconds(0.06 * index)
        voice = tone(frequency, length - start, (1.0, 0.22), detune=1.5,
                     seed=51 + index)
        shimmer[start:] += voice * envelope(
            length - start, 0.02, 0.24, 0.3, 0.4)
    return shimmer / 2.4


def level_up() -> np.ndarray:
    length = seconds(0.95)
    chord = np.zeros(length)
    for index, frequency in enumerate((392.0, 523.25, 659.25)):
        start = seconds(0.12 * index)
        chord[start:] += tone(frequency, length - start, (1.0, 0.4, 0.15)) \
            * envelope(length - start, 0.02, 0.3, 0.35, 0.45)
    return chord / 2.2


def world_effect() -> np.ndarray:
    length = seconds(0.5)
    swarm = noise(length, seed=61, smoothing=8) * 0.5
    drone = tone(210.0, length, (1.0, 0.7, 0.4), detune=9.0, seed=62) * 0.5
    return (swarm + drone) * envelope(length, 0.04, 0.2, 0.4, 0.26)


RECIPES = {
    "ui_click": ui_click,
    "ui_close": ui_close,
    "harvest_start": harvest_start,
    "harvest_gather": harvest_gather,
    "item_pickup": item_pickup,
    "combat_hit": combat_hit,
    "combat_miss": combat_miss,
    "spell_cast": spell_cast,
    "level_up": level_up,
    "world_effect": world_effect,
}


def write_wav(path: Path, samples: np.ndarray) -> int:
    peak = float(np.max(np.abs(samples))) or 1.0
    scaled = np.clip(samples / peak * PEAK, -1.0, 1.0)
    pcm = (scaled * 32767.0).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(pcm.tobytes())
    return pcm.size


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out", type=Path,
        default=Path(__file__).resolve().parents[2] / "godot-client" / "assets"
        / "audio")
    arguments = parser.parse_args()
    catalog = {"schema": "eloria.sounds/1", "sampleRate": SAMPLE_RATE,
               "sounds": []}
    for name in sorted(RECIPES):
        samples = RECIPES[name]()
        written = write_wav(arguments.out / f"{name}.wav", samples)
        catalog["sounds"].append({
            "name": name, "file": f"{name}.wav",
            "seconds": round(written / SAMPLE_RATE, 3)})
        print(f"{name}: {written} samples")
    (arguments.out / "catalog.json").write_text(
        json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(catalog['sounds'])} sounds to {arguments.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
