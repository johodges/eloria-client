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


# --- ambience -----------------------------------------------------------------
#
# Loops the world manifests already name in `environment.ambientAudio`. They
# are built to loop: the first and last 0.4 seconds cross-fade into each other,
# so a repeat has no seam.


def _loop(samples: np.ndarray, fade: float = 0.4) -> np.ndarray:
    count = min(int(fade * SAMPLE_RATE), samples.size // 4)
    if count <= 0:
        return samples
    ramp = np.linspace(0.0, 1.0, count)
    head, tail = samples[:count], samples[-count:]
    body = samples[count:-count]
    return np.concatenate([tail * (1.0 - ramp) + head * ramp, body])


def civic_crowd() -> np.ndarray:
    """A town's murmur: broad low noise with a few slow voices over it."""
    length = seconds(12.0)
    murmur = noise(length, seed=71, smoothing=220) * 0.7
    voices = np.zeros(length)
    generator = np.random.default_rng(72)
    for index in range(9):
        start = int(generator.uniform(0.0, 10.5) * SAMPLE_RATE)
        span = seconds(float(generator.uniform(0.35, 0.9)))
        span = min(span, length - start)
        if span <= 0:
            continue
        voice = tone(float(generator.uniform(150.0, 320.0)), span,
                     (1.0, 0.5, 0.25), detune=3.0, seed=73 + index)
        voices[start:start + span] += voice * envelope(
            span, 0.08, 0.2, 0.4, 0.3) * 0.35
    return _loop(murmur + voices)


def waterfall() -> np.ndarray:
    """Falling water: wide noise with a slow swell, no tonal centre."""
    length = seconds(10.0)
    body = noise(length, seed=81, smoothing=6) * 0.85
    low = noise(length, seed=82, smoothing=300) * 0.5
    swell = 0.85 + 0.15 * np.sin(
        2.0 * np.pi * 0.11 * np.arange(length) / SAMPLE_RATE)
    return _loop((body + low) * swell)


# --- music --------------------------------------------------------------
#
# Three ambient beds, each a slow chord cycle over a drone. They are built the
# same way as everything else here - sine partials and shaped noise - so they
# are original by construction, and looped seamlessly so a track can play under
# a map indefinitely without a seam.
#
# The tuning is A = 432 Hz rather than 440, which is a deliberate choice for
# this world's sound and not borrowed from anywhere.

ROOT = 432.0 / 4.0


def _chord_bed(chords, seed: int, bar_seconds: float, air: float,
               brightness: float) -> np.ndarray:
    """A cycle of chords over a held root, with a breath of noise over it."""
    bar = seconds(bar_seconds)
    length = bar * len(chords)
    body = np.zeros(length)
    partials = (1.0, 0.42 * brightness, 0.18 * brightness, 0.08 * brightness)
    for index, chord in enumerate(chords):
        start = index * bar
        for step, ratio in enumerate(chord):
            voice = tone(ROOT * ratio, bar, partials, detune=0.6,
                         seed=seed + index * 7 + step)
            body[start:start + bar] += voice * envelope(
                bar, bar_seconds * 0.35, bar_seconds * 0.25, 0.55,
                bar_seconds * 0.4) * (0.30 if step else 0.22)
    drone = tone(ROOT * 0.5, length, (1.0, 0.3, 0.1), detune=0.3,
                 seed=seed + 101) * 0.24
    breath = noise(length, seed=seed + 211, smoothing=420) * air
    swell = 0.88 + 0.12 * np.sin(
        2.0 * np.pi * 0.035 * np.arange(length) / SAMPLE_RATE)
    return _loop((body + drone + breath) * swell, fade=1.6)


def music_settlement() -> np.ndarray:
    """Somewhere with people in it: warm, major, unhurried."""
    return _chord_bed(
        [(1.0, 1.25, 1.5), (1.125, 1.5, 1.875), (0.75, 1.0, 1.25),
         (1.0, 1.25, 1.5)],
        seed=310, bar_seconds=7.0, air=0.05, brightness=1.0)


def music_wilds() -> np.ndarray:
    """Open country: modal, wider intervals, more air."""
    return _chord_bed(
        [(1.0, 1.2, 1.5), (0.888, 1.2, 1.333), (1.0, 1.333, 1.5),
         (0.75, 1.125, 1.5)],
        seed=420, bar_seconds=8.5, air=0.09, brightness=0.72)


def music_depths() -> np.ndarray:
    """Underground and interiors: low, close, unresolved."""
    return _chord_bed(
        [(0.5, 0.75, 1.2), (0.5, 0.8, 1.0), (0.5, 0.703, 1.0),
         (0.5, 0.75, 1.125)],
        seed=530, bar_seconds=9.0, air=0.04, brightness=0.45)


def footstep() -> np.ndarray:
    """One step: a short broadband tap with a soft low body."""
    length = seconds(0.16)
    tap = noise(length, seed=91, smoothing=4) * 0.7
    body = tone(96.0, length, (1.0, 0.5)) * 0.5
    return (tap + body) * envelope(length, 0.002, 0.06, 0.25, 0.09)


RECIPES = {
    "civic_crowd": civic_crowd,
    "waterfall": waterfall,
    "footstep": footstep,
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

MUSIC = {
    "music_settlement": music_settlement,
    "music_wilds": music_wilds,
    "music_depths": music_depths,
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
               "sounds": [], "music": []}
    for name in sorted(RECIPES):
        samples = RECIPES[name]()
        written = write_wav(arguments.out / f"{name}.wav", samples)
        catalog["sounds"].append({
            "name": name, "file": f"{name}.wav",
            "seconds": round(written / SAMPLE_RATE, 3)})
        print(f"{name}: {written} samples")
    for name in sorted(MUSIC):
        samples = MUSIC[name]()
        written = write_wav(arguments.out / f"{name}.wav", samples)
        catalog["music"].append({
            "name": name.removeprefix("music_"), "file": f"{name}.wav",
            "seconds": round(written / SAMPLE_RATE, 3)})
        print(f"{name}: {written} samples")
    (arguments.out / "catalog.json").write_text(
        json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(catalog['sounds'])} sounds and"
          f" {len(catalog['music'])} music beds to {arguments.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
