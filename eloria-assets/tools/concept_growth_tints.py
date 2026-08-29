#!/usr/bin/env python3
"""Measure the colour of what is *growing* on each creature in the concept art.

The growth palette was being derived from the kind of growth alone -- leaf is
green, moss is green -- which is right for the jungle and wrong everywhere
else.  The Amberwood sheets are an autumn wood: their foliage measures amber
(126, 92, 40), and the thornwood dryad's is crimson.  Painting those green is
the single most visible colour error in the library.

This samples the saturated mid-to-bright pixels of a cut concept figure,
excluding whatever matches the creature's own body palette, and reports the
dominant hue cluster.  Feed the output into ``creature_roster.GROWTH_TINT``.

    ELORIA_CONCEPT_FIGURES=/path/to/figures \\
        python3 eloria-assets/tools/concept_growth_tints.py --table
"""
from __future__ import annotations

import argparse
import colorsys
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import numpy as np
from PIL import Image

import concept_figures as CF
import creature_roster as RO


# Growth that is actually vegetation.  Crystal, rime, coral, barnacle and plate
# already take their colour from the creature's own palette.
PLANT = {"leaf", "vine", "moss", "thorn", "fungus"}


def plausible_foliage(rgb) -> bool:
    """Leaves are never blue.  Reject clusters that are the creature glowing."""
    red, green, blue = rgb
    # Foliage is warm or neutral; anything cooler than it is warm is the
    # creature's own glow -- a spectral knight's teal, a drake's jade.
    return red >= blue and blue <= max(red, green)


def growth_tint(slug: str, bins: int = 12):
    """(rgb, share) of the dominant saturated hue cluster, or None."""
    path = CF.figure_path(slug)
    if path is None:
        return None
    image = Image.open(path).convert("RGBA")
    array = np.asarray(image)
    opaque = array[..., 3] > 120
    rgb = array[..., :3][opaque].astype(float)
    if not len(rgb):
        return None
    high = rgb.max(axis=1)
    low = rgb.min(axis=1)
    saturation = (high - low) / np.maximum(high, 1.0)
    picked = rgb[(saturation > .35) & (high > 90)]
    if len(picked) < 64:
        return None
    # Subsample for speed; the clusters are large and stable under it.
    step = max(1, len(picked) // 4000)
    sample = picked[::step]
    buckets: dict[int, list] = {}
    for colour in sample:
        hue = colorsys.rgb_to_hsv(*(colour / 255.0))[0]
        buckets.setdefault(int(hue * bins) % bins, []).append(colour)
    key = max(buckets, key=lambda k: len(buckets[k]))
    mean = np.mean(buckets[key], axis=0)
    return (tuple(int(round(v)) for v in mean), len(buckets[key]) / len(sample))


def core_tint(slug: str, quantile: float = .965):
    """The colour of the brightest lit thing on a figure -- its glowing core.

    Treant hearts, wisp centres and lit carapaces are the brightest ink on the
    sheet by a wide margin, so the top of the luminance distribution isolates
    them.  Pure white is dropped: that is specular bloom, not the light's hue.
    """
    path = CF.figure_path(slug)
    if path is None:
        return None
    array = np.asarray(Image.open(path).convert("RGBA"))
    rgb = array[..., :3][array[..., 3] > 120].astype(float)
    if len(rgb) < 64:
        return None
    luma = rgb @ np.array((.2126, .7152, .0722))
    picked = rgb[luma >= np.quantile(luma, quantile)]
    high = picked.max(axis=1)
    low = picked.min(axis=1)
    # The very top of the range is specular bloom and carries no hue at all;
    # the light's actual colour is the saturated ink just under it.
    coloured = picked[(high - low) / np.maximum(high, 1.0) > .22]
    if len(coloured) < 8:
        coloured = picked
    return tuple(int(round(v)) for v in coloured.mean(axis=0))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slugs", nargs="*")
    parser.add_argument("--core", action="store_true",
                        help="report the colour of the figure's brightest lit "
                             "feature instead of its foliage")
    parser.add_argument("--table", action="store_true",
                        help="print a GROWTH_TINT table for every creature "
                             "the roster says something grows on")
    args = parser.parse_args()
    slugs = args.slugs or (sorted(RO.GROWTH) if args.table else [])
    if not slugs:
        parser.error("name creatures, or pass --table")
    if args.core:
        for slug in slugs:
            found = core_tint(slug)
            print(f'    "{slug}": {found},' if found else f"    # {slug}: no figure")
        return
    for slug in slugs:
        if args.table and not PLANT.issuperset(
                {kind for kind, _, _ in RO.GROWTH.get(slug, [])}):
            # Mineral growth already tracks the creature's own palette, and on
            # those figures the dominant hue is the body rather than the crust.
            continue
        found = growth_tint(slug)
        if found is None:
            print(f"    # {slug}: no figure")
            continue
        rgb, share = found
        if args.table and not plausible_foliage(rgb):
            # A blue or violet cluster is the creature glowing, not its leaves.
            print(f"    # {slug}: dominant hue {rgb} is not foliage")
            continue
        if args.table:
            print(f'    "{slug}": {rgb},'.ljust(52) + f"# {share:.0%} of the ink")
        else:
            print(f"{slug:26s} {rgb}  {share:.0%}")


if __name__ == "__main__":
    main()
