"""Reach links: authored ground written onto the finished composition so the served walk grid joins its areas.

The seventeenth contracts run (2026-09-17) refused placements that bands of ground steeper than the walkable .65
grade cut off from their territory's arrival. A plan terrain edit cannot link them reliably: it applies before the
foundations and the roads, so a road that re-routes onto the gentle ground it makes, or a footing feather, grades it
again. A reach link is the same authored shape as a terrain edit (landscape's ramp, flatten, raise or lower, with its
feather and strength), listed under the plan's "reach_links", and applied once the roads are settled and the support
stages have finished the ground: nothing after it moves the ground but the road heights refreshed onto it and the
placements regrounded on it. It never reaches a river's centreline (the carved beds and the bridge banks stay as the
drainage made them) and never moves the ground under a rigid compound's member by more than a quarter metre (reground
does not move compound members; a tree member's ground is the three metres round its trunk, not its canopy's box).
"""
from __future__ import annotations

import numpy as np

import landscape as L

PLAN_KEY = 'reach_links'


def links(plan):
    return list(plan.get(PLAN_KEY) or [])


def validate_reach_links(plan):
    """Every problem with the plan's reach links, in the terrain edit validator's words; empty means valid."""
    value = plan.get(PLAN_KEY)
    if value is None:
        return []
    if not isinstance(value, list):
        return [f"'{PLAN_KEY}' must be a list of links"]
    problems = L.validate_terrain_edits({'terrain_edits': value, 'bounds': plan.get('bounds')})
    return [problem.replace('terrain edit', 'reach link') for problem in problems]


def river_contacts(plan, link):
    """(river id, largest weight) for every plan river whose centreline the link's weight reaches."""
    contacts = []
    for river in plan.get('rivers') or []:
        if len(river.get('points') or []) < 2:
            continue
        # The channel's own centreline: the plan's Catmull-Rom curve, sampled at a metre or finer.
        curve = np.asarray(L.curved_points(river['points']), dtype=float)[:, :2]
        points = [curve[:1]]
        for a, b in zip(curve[:-1], curve[1:]):
            count = max(1, int(np.ceil(np.linalg.norm(b - a))))
            points.append(a + (b - a) * (np.arange(1, count + 1)[:, None] / count))
        points = np.vstack(points)
        weight = np.asarray(L._edit_weight(points[:, 0], points[:, 1], link), dtype=float)
        if (weight > 0).any():
            contacts.append((river.get('id'), float(weight.max())))
    return contacts


COMPOUND_TOLERANCE_METRES = .25   # the ground under a rigid compound member may move this little, as a seat settles
TRUNK_RADIUS_METRES = 3.          # a tree member's ground: this far round its pivot, not its canopy's box


def trunk_pivot(obj):
    """Where a tree member meets the ground: its source pivot carried by its shift, else its box centre."""
    if obj.get('sourcePivot') is not None and obj.get('shift') is not None:
        return np.asarray(obj['sourcePivot'], dtype=float) + np.asarray(obj['shift'], dtype=float)
    return (np.asarray(obj['low'], dtype=float) + np.asarray(obj['high'], dtype=float)) * .5


def compound_contacts(world, content, change):
    """(region, node, metres) of rigid compound members over whose footprint the ground ``change`` (a composed-grid
    array of metres) exceeds COMPOUND_TOLERANCE_METRES: reground does not move a compound member with its ground."""
    if content is None:
        return []
    found = []
    for obj in getattr(content, 'objects', []):
        if not obj.get('assembly'):
            continue
        low, high = np.asarray(obj['low'], dtype=float), np.asarray(obj['high'], dtype=float)
        if obj.get('kind') == 'tree':
            # A tree stands on its trunk: its box is the canopy's, metres wider than the ground it touches.
            pivot = trunk_pivot(obj)
            low = np.array([pivot[0] - TRUNK_RADIUS_METRES, 0., pivot[2] - TRUNK_RADIUS_METRES])
            high = np.array([pivot[0] + TRUNK_RADIUS_METRES, 0., pivot[2] + TRUNK_RADIUS_METRES])
        under = (world.gx >= low[0] - 1.) & (world.gx <= high[0] + 1.) & (world.gz >= low[2] - 1.) & (world.gz <= high[2] + 1.)
        if not under.any():
            continue
        moved = float(np.max(change[under]))
        if moved > COMPOUND_TOLERANCE_METRES:
            found.append((obj.get('region'), obj.get('node'), round(moved, 3)))
    return found


def apply_reach_links(world, content=None):
    """Write the plan's reach links onto the composed ground, in list order; returns and records the report."""
    authored = links(world.plan)
    problems = validate_reach_links(world.plan)
    if problems:
        raise ValueError('Reach links: ' + '; '.join(problems))
    report = {'links': len(authored), 'perLink': []}
    if not authored:
        world.reach_links = report
        return report
    for link in authored:
        rivers = river_contacts(world.plan, link)
        if rivers:
            raise ValueError(f"Reach link {link['id']!r} reaches river centrelines {rivers}; keep its shape and feather off the channel")
    before = np.asarray(world.height, dtype=float).copy()
    height = before
    for link in authored:
        after = L._terrain_edit_height(world.gx, world.gz, height, {'terrain_edits': [link]})
        changed = np.abs(after - height)
        compounds = compound_contacts(world, content, changed)
        if compounds:
            raise ValueError(f"Reach link {link['id']!r} moves the ground under rigid compound members {compounds[:6]} by more than "
                             f"{COMPOUND_TOLERANCE_METRES} m; reground cannot move them with it")
        report['perLink'].append({'id': link['id'], 'op': link.get('op'), 'changedCells': int((changed > .01).sum()),
                                  'maximumChangeMetres': round(float(changed.max(initial=0.)), 3)})
        height = after
    world.height = height
    total = np.abs(height - before)
    report.update(changedCells=int((total > .01).sum()), maximumChangeMetres=round(float(total.max(initial=0.)), 3))
    world.reach_links = report
    return report
