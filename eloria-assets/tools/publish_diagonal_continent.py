"""Publish one exported continent into stable, named server territories.

The exporter owns geometry and explicit standing-point placements. This tool
owns paired coordinate contracts, never invents content identities, and never
opens a live database. Dry run is the default. --apply writes a validated plan;
--build additionally folds strict authored collision, writes ELMs, regenerates
invasion candidates, and publishes final package digests in sequential steps.
Run through the task's run_limited.py so child builds inherit its CPU ceiling.
"""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys

import publish_continent_geography as shared

CLIENT = Path(__file__).resolve().parents[2]
PUBLICATION = CLIENT / 'eloria-assets/maps/nymara-regions/_continent/publication.json'
STATE = 'diagonalContinent'
BEGIN = '# --- Diagonal continent crossings: generated from the shared continent ---'
END = '# --- end diagonal continent crossings ---'
CONTENT = {'npcs.txt': ('npc', 2, 3, 4, 'npcs', 1),
           'harvesting.txt': ('node', 1, 3, 4, 'harvest', 2),
           'spawns.txt': ('spawn', 1, 3, 4, 'spawns', None),
           'interactives.txt': (None, 0, 2, 3, 'interactives', 1)}
TILE_FIELDS = {'serverTile', 'server_tile', 'arrival', 'spawnTile', 'destinationTile',
               'targetTile', 'returnTile', 'exitTile'}
WORLD_FIELDS = {'targetPosition', 'destinationPosition', 'returnPosition'}


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def resolve_input(client, publication, value):
    path = Path(value)
    if not path.is_absolute():
        path = publication.parent / path
    path = path.resolve()
    if not path.is_relative_to(client.resolve()):
        raise ValueError(f'Export input escapes the client checkout: {path}')
    if not path.is_file():
        raise ValueError(f'Missing exported continent input: {path}')
    return path


def point_key(point):
    x, y = shared.integer_pair(point, 'standing point')
    return f'{x}:{y}'


def content_local(transform, x, z, translation):
    """A source point (x, z) in continent metres relative to the territory's centre.

    ``scale`` about ``sourceCenter``, plus ``targetCenter``, is the rule for a layout that only scales. A layout
    that turns or squeezes per axis publishes ``scale`` null with its exact ``affine`` [a, b, c, d, e, f]:
    continent X = a*x + b*z + e and Z = c*x + d*z + f in absolute metres, so the centre, the spec's
    ``translation``, comes off it."""
    scale = transform['scale']
    if scale is None:
        a, b, c, d, e, f = transform['affine']
        return a * x + b * z + e - translation[0], c * x + d * z + f - translation[2]
    source, target = transform['sourceCenter'], transform['targetCenter']
    return (x - source[0]) * scale + target[0], (z - source[1]) * scale + target[1]


def transform_tile(point, spec):
    explicit = spec.get('tilePositions', {}).get(point_key(point))
    if explicit is not None:
        return list(shared.integer_pair(explicit, 'exact standing point'))
    old = spec['previousServerOrigin']
    origin = spec['serverOrigin']
    # Server coordinates name cell centres; server Y runs opposite local Z.
    x, z = content_local(spec['contentTransform'], point[0] + .5 - old[0], old[1] - point[1] - .5, spec.get('translation'))
    return [math.floor(x + origin[0]), math.floor(origin[1] - z)]


def world_point(region, tile, specs):
    spec = specs[region]
    return (round(tile[0] + .5 - spec['serverOrigin'][0] + spec['translation'][0], 6),
            round(spec['serverOrigin'][1] - tile[1] - .5 + spec['translation'][2], 6))


def validate_spec(region, spec, previous):
    for name in ('serverOrigin', 'previousServerOrigin', 'serverCells', 'arrival'):
        spec[name] = list(shared.integer_pair(spec.get(name), f'{region}.{name}'))
    size = spec['serverCells']
    if size[0] != size[1] or size[0] <= 0 or size[0] % 6:
        raise ValueError(f'{region}: served envelope must be square and divisible by six')
    if previous and spec['previousServerOrigin'] != previous.get('serverOrigin'):
        raise ValueError(f'{region}: export was authored against a different server address frame')
    transform = spec.get('contentTransform', {})
    if transform.get('scale') is None and 'scale' in transform:
        affine = transform.get('affine')
        if (not isinstance(affine, list) or len(affine) != 6
                or not all(isinstance(n, (int, float)) and not isinstance(n, bool) and math.isfinite(n) for n in affine)):
            raise ValueError(f'{region}: a contentTransform with no uniform scale requires its exact affine')
        if affine[0] * affine[3] - affine[1] * affine[2] <= 0:
            raise ValueError(f'{region}: contentTransform affine must keep orientation and area')
    elif not isinstance(transform.get('scale'), (int, float)) or transform['scale'] <= 0:
        raise ValueError(f'{region}: contentTransform requires a positive uniform scale')
    for key in ('sourceCenter', 'targetCenter'):
        if len(transform.get(key, [])) != 2 or not all(isinstance(n, (int, float)) and math.isfinite(n) for n in transform[key]):
            raise ValueError(f'{region}: contentTransform.{key} requires two finite coordinates')
    translation = spec.get('translation', [])
    if len(translation) != 3 or not all(isinstance(n, (int, float)) and math.isfinite(n) for n in translation):
        raise ValueError(f'{region}: translation requires three finite coordinates')
    if not spec.get('terrainRevision'):
        raise ValueError(f'{region}: reshaped terrain must declare a save migration revision')
    spec.setdefault('tilePositions', {})
    for portal, value in spec.get('portalPositions', {}).items():
        if not isinstance(value, dict) or 'oldTile' not in value or 'tile' not in value:
            raise ValueError(f'{region}.{portal}: portalPositions requires oldTile and tile')
        spec['tilePositions'][point_key(value['oldTile'])] = list(shared.integer_pair(value['tile'], portal))


def rewrite_content(text, filename, specs, repeated):
    keyword, mi, xi, yi, group, identity_index = CONTENT[filename]
    rows, counts, used, retired = [], {}, {}, {}
    for line in text.splitlines(keepends=True):
        fields = line.split('|')
        if line.lstrip().startswith('#') or len(fields) <= max(mi, xi, yi):
            rows.append(line)
            continue
        region = fields[mi].strip()
        if region not in specs or keyword is not None and fields[0].strip() != keyword:
            rows.append(line)
            continue
        old = [int(fields[xi]), int(fields[yi])]
        ordinal = counts.get(region, 0)
        counts[region] = ordinal + 1
        identity = str(ordinal) if identity_index is None else fields[identity_index].strip()
        spec = specs[region]
        if filename == 'interactives.txt' and identity in {str(value) for value in spec.get('removedInteractiveIds', [])}:
            if len(fields) < 6 or fields[4].strip() != 'portal' or fields[5].strip() != 'maps.txt':
                raise ValueError(f'{region}.{identity}: only obsolete generic portal interactives can be removed')
            retired.setdefault(region, set()).add(identity)
            continue
        used.setdefault(region, set()).add(identity)
        explicit = spec.get('contentPositions', {}).get(group, {}).get(identity)
        new = (list(shared.integer_pair(explicit, f'{region}.{group}.{identity}')) if explicit is not None
               else old if repeated else transform_tile(old, spec))
        if not repeated:
            key = point_key(old)
            existing = spec['tilePositions'].get(key)
            if existing is not None and list(existing) != new:
                raise ValueError(f'{region}: conflicting authored destinations for standing point {key}')
            spec['tilePositions'][key] = new
        fields[xi], fields[yi] = shared.field_number(fields[xi], new[0]), shared.field_number(fields[yi], new[1])
        rows.append('|'.join(fields))
    for region, spec in specs.items():
        expected = set(spec.get('contentPositions', {}).get(group, {}))
        if filename == 'interactives.txt':
            expected -= {str(value) for value in spec.get('removedInteractiveIds', [])}
        missing = expected - used.get(region, set()) - retired.get(region, set())
        if missing:
            raise ValueError(f'{region}.{group}: exported identities absent from the source profile: {sorted(missing)}')
        if filename == 'interactives.txt' and not repeated:
            missing = {str(value) for value in spec.get('removedInteractiveIds', [])} - retired.get(region, set())
            if missing:
                raise ValueError(f'{region}: removedInteractiveIds absent from source profile: {sorted(missing)}')
    return ''.join(rows), counts


def runtime_specs(specs, previous):
    result = {}
    for region, spec in specs.items():
        legacy = previous.get(region, {})
        result[region] = {key: copy.deepcopy(spec[key]) for key in (
            'serverOrigin', 'serverCells', 'arrival', 'translation', 'terrainRevision')}
        result[region].update(nativeServerOrigin=legacy.get('nativeServerOrigin', spec['previousServerOrigin']),
                              nativeServerCells=legacy.get('nativeServerCells', spec['serverCells']),
                              previousServerOrigin=spec['previousServerOrigin'],
                              contentTransform=copy.deepcopy(spec['contentTransform']))
        if legacy.get('nativeRevision'):
            result[region]['nativeRevision'] = legacy['nativeRevision']
    return result


def placement_contracts(specs):
    """Vendor immutable landmark correspondence for standalone server checks.

    Keep the baseline table on later publications: tilePositions is then keyed
    by the previous diagonal layout, not by the original semantic source frame.
    """
    return {region: {
        'baselineServerOrigin': copy.deepcopy(spec.get('baselineServerOrigin', spec['previousServerOrigin'])),
        'baselineTilePositions': copy.deepcopy(spec.get('baselineTilePositions', spec.get('tilePositions', {}))),
        'baselineContentTransform': copy.deepcopy(spec.get('baselineContentTransform', spec['contentTransform'])),
        'contentPositions': copy.deepcopy(spec.get('contentPositions', {})),
        'portalPositions': copy.deepcopy(spec.get('portalPositions', {})),
    } for region, spec in specs.items()}


def rewrite_exact_arrivals(text, kind, specs):
    edit = shared.SourceEdits(text)
    if kind == 'generator':
        edit.replace(edit.assignment('FOUR_GATES_TILES_WIDE'), specs['four_gates']['serverCells'][0] // 6)
        for name, field in (('MAP_TILES_WIDE_BY_NAME', 'serverCells'), ('ARRIVAL_TILES', 'arrival')):
            node = edit.assignment(name)
            for key, value in zip(node.keys, node.values):
                region = ast.literal_eval(key) if key else None
                if region in specs:
                    edit.replace(value, specs[region][field][0] // 6 if field == 'serverCells' else tuple(specs[region][field]))
    else:
        edit.replace(edit.assignment('FOUR_GATES_ARRIVAL'), tuple(specs['four_gates']['arrival']))
        for name in ('COASTAL_ARRIVALS', 'SOUTHERN_ARRIVALS'):
            node = edit.assignment(name)
            for key, value in zip(node.keys, node.values):
                region = ast.literal_eval(key)
                if region in specs and not isinstance(value, ast.Name):
                    edit.replace(value, tuple(specs[region]['arrival']))
    return edit.finish()


def rewrite_gameplay_source(text, kind, mappings):
    if kind not in ('world', 'walkthrough'):
        return shared.rewrite_python(text, kind, mappings)
    edit = shared.SourceEdits(text)
    if kind == 'walkthrough':
        node = edit.assignment('PLAZA')
        edit.replace(node, tuple(shared.shifted(ast.literal_eval(node), 'four_gates', mappings)))
    else:
        node = edit.assignment('TUTORIAL_ROUTE_MARKERS')
        edit.replace(node, tuple(tuple(shared.shifted(point, 'four_gates', mappings)) for point in ast.literal_eval(node)))
        node = edit.assignment('TUTORIAL_HARVESTS')
        edit.replace(node, tuple((point[0], *shared.shifted(point[1:3], 'four_gates', mappings), *point[3:])
                                 for point in ast.literal_eval(node)))
    return edit.finish()


def remap_metadata(value, specs, mapping, region=None):
    if isinstance(value, list):
        return [remap_metadata(item, specs, mapping, region) for item in value]
    if not isinstance(value, dict):
        return value
    own = value.get('map_id', value.get('map', region))
    result = {}
    for key, item in value.items():
        if key in (STATE, 'continentGeography', 'geographicFamily'):
            result[key] = item
            continue
        target = own
        if key in ('destinationTile', 'destinationPosition', 'targetTile', 'targetPosition'):
            target = value.get('destinationMap', value.get('destination', value.get('targetMap')))
        elif key in ('returnTile', 'exitTile', 'returnPosition'):
            target = value.get('returnMap', value.get('exitMap', value.get('exit_map')))
        if key in TILE_FIELDS and target in specs and isinstance(item, list) and len(item) == 2:
            result[key] = shared.shifted(item, target, mapping)
        elif key in WORLD_FIELDS and target in specs and isinstance(item, list) and len(item) == 3:
            spec = specs[target]
            old = [math.floor(item[0] + spec['previousServerOrigin'][0]),
                   math.floor(spec['previousServerOrigin'][1] - item[2])]
            tile = shared.shifted(old, target, mapping)
            height=spec.get('tileHeights',{}).get(f'{tile[0]}:{tile[1]}',item[1])
            result[key] = [tile[0] + .5 - spec['serverOrigin'][0], height,
                           spec['serverOrigin'][1] - tile[1] - .5]
        else:
            result[key] = remap_metadata(item, specs, mapping, own)
    return result


def connection_rows(connections, specs):
    lines, entries, identities, sources = [], [], set(), set()
    for connection in connections:
        identity = connection['id']
        if identity in identities or len(connection.get('ends', [])) != 2:
            raise ValueError(f'{identity}: connection identity must be unique with two ends')
        identities.add(identity)
        a, b = connection['ends']
        if a['region'] not in specs or b['region'] not in specs or a['region'] == b['region']:
            raise ValueError(f'{identity}: connection must join two exported territories')
        seamless = connection.get('type', 'land') not in ('ferry', 'ship', 'boat', 'teleport')
        lines.append(f'# {identity} ({connection.get("type", "land")})\n')
        for source, destination in ((a, b), (b, a)):
            lanes = source.get('lanes', [{'tile': source['tile'], 'arrival': source['arrival']}])
            arrivals = destination.get('lanes', [{'tile': destination['tile'], 'arrival': destination['arrival']}])
            targets = {world_point(destination['region'], lane['arrival'], specs): lane['arrival'] for lane in arrivals}
            for lane in lanes:
                tile = list(shared.integer_pair(lane['tile'], identity + ' departure'))
                arrival = targets.get(world_point(source['region'], tile, specs)) if seamless else destination['arrival']
                if arrival is None:
                    raise ValueError(f'{identity}: source lane {tile} has no arrival at the same global cell centre')
                arrival = list(shared.integer_pair(arrival, identity + ' arrival'))
                trigger = (source['region'], *tile)
                if trigger in sources:
                    raise ValueError(f'{identity}: duplicate exterior departure {trigger}')
                sources.add(trigger)
                entries.append((source['region'], *tile, destination['region'], *arrival))
                lines.append('portal | ' + ' | '.join(map(str, entries[-1])) + '\n')
    for source, x, y, target, tx, ty in entries:
        if (target, tx, ty) in sources:
            raise ValueError(f'{source}->{target}: arrival immediately triggers another exterior crossing')
    return ''.join(lines), entries


def replace_crossings(text, connections, specs):
    if BEGIN in text:
        if END not in text:
            raise ValueError('Previous diagonal crossing block is incomplete')
        start, stop = text.index(BEGIN), text.index(END) + len(END)
        text = text[:start] + text[stop:]
    rows = []
    for line in text.splitlines(keepends=True):
        fields = [field.strip() for field in line.split('|')]
        if len(fields) in (7, 8) and fields[0] == 'portal':
            mi = 4 if len(fields) == 7 else 5
            if fields[1] in specs and fields[mi] in specs:
                continue
        rows.append(line)
    emitted, entries = connection_rows(connections, specs)
    return ''.join(rows).rstrip() + '\n\n' + BEGIN + '\n' + emitted + END + '\n', entries


def validate_standing_points(specs, blobs, texts, connections):
    """Reject blocked/out-of-envelope content; never repair geometry silently."""
    grids = {}
    for region, spec in specs.items():
        blob = blobs[region]
        magic, version, _, width, height = struct.unpack_from('<4sHHII', blob)
        if magic != b'EWCG' or version != 2 or [width, height] != [n * 2 for n in spec['serverCells']]:
            raise ValueError(f'{region}: exported EWCGv2 dimensions do not match the served frame')
        if len(blob) < 16 + width * height:
            raise ValueError(f'{region}: truncated collision payload')
        grids[region] = (width, blob[16:16 + width * height])
    checked = set()
    def check(region, point, label):
        if region not in specs:
            return
        x, y = shared.integer_pair(point, label)
        width, height = specs[region]['serverCells']
        if not (0 <= x < width and 0 <= y < height):
            raise ValueError(f'{label}: {region} tile {(x, y)} is outside its served envelope')
        stride, data = grids[region]
        at = 2 * y * stride + 2 * x
        if not all(data[index] for index in (at, at + 1, at + stride, at + stride + 1)):
            raise ValueError(f'{label}: {region} tile {(x, y)} is blocked by the authored collision')
        checked.add((region, x, y))
    for region, spec in specs.items():
        check(region, spec['arrival'], 'safe arrival')
    for filename, rules in shared.RULES.items():
        for number, line in enumerate(texts.get(filename, '').splitlines(), 1):
            if line.lstrip().startswith('#'):
                continue
            fields = [f.strip() for f in line.split('|')]
            for keyword, mi, xi, yi in rules:
                if len(fields) <= max(mi, xi, yi):
                    continue
                matches = (fields[0] == 'portal' and len(fields) == int(keyword[-1])
                           if keyword and keyword.startswith('portal') else keyword is None or fields[0] == keyword)
                # Area rectangle corners bound a zone and need not be walkable.
                if matches and filename != 'special_areas.txt':
                    check(fields[mi], [int(fields[xi]), int(fields[yi])], f'{filename}:{number}')
    return len(checked)


def connection_manifests(publication, worlds, specs):
    graph, streaming = [], []
    for connection in publication['connections']:
        a, b = connection['ends']
        graph.append({'id': connection['id'], 'from': a['region'], 'from_portal': a['portal'],
                      'to': b['region'], 'to_portal': b['portal'], 'type': connection.get('type', 'land'),
                      'note': connection.get('note', 'Shared-continent authored connection')})
        if connection.get('type', 'land') in ('ferry', 'ship', 'boat', 'teleport'):
            continue
        ends = []
        for end in (a, b):
            region = end['region']
            world = worlds[region]
            frame = end.get('frame') or next((frame for frame in world.get('streamingBorders', [])
                                              if frame.get('portal') == end['portal']), None)
            if not frame:
                raise ValueError(f'{connection["id"]}: exported land crossing lacks its authored frame')
            tile, origin = end['tile'], specs[region]['serverOrigin']
            position = end.get('position', [tile[0] + .5 - origin[0], frame['anchor'][1], origin[1] - tile[1] - .5])
            ends.append({'map': region, 'portal': end['portal'], 'position': position,
                         'frame': copy.deepcopy(frame), 'coordinateTransform': copy.deepcopy(world['coordinateTransform']),
                         'preloadEdges':copy.deepcopy(end.get('preloadEdges',[]))})
        streaming.append({'id': connection['id'], 'seamless': True, 'ends': ends})
    identities={c['id'] for c in streaming}
    for visual in publication.get('visualConnections',[]):
        if visual.get('id') in identities or len(visual.get('ends',[]))!=2 or not visual.get('visualOnly'):
            raise ValueError('Visual adjacency requires a unique identity, two ends, and visualOnly=true')
        entry=copy.deepcopy(visual)
        for end in entry['ends']:
            if end.get('map') not in worlds or not end.get('preloadEdges') or not end.get('frame'):
                raise ValueError('Visual adjacency requires existing territories and surveyed edges/frames')
            end['coordinateTransform']=copy.deepcopy(worlds[end['map']]['coordinateTransform'])
        identities.add(entry['id']);streaming.append(entry)
    settings = {key: publication.get(key, default) for key, default in (
        ('preloadDistance', 320), ('retainDistance', 420), ('maximumNeighbours', 3))}
    return ({'schema': 1, 'revision': publication['revision'], 'connections': graph},
            {'schema': 1, **settings, 'connections': streaming})


def plan(client, server, publication_path):
    client, server, publication_path = client.resolve(), server.resolve(), publication_path.resolve()
    raw = publication_path.read_bytes()
    publication = json.loads(raw)
    if publication.get('schema') != 1 or not publication.get('revision') or not publication.get('regions'):
        raise ValueError('Publication requires schema 1, a revision and named territories')
    master = resolve_input(client, publication_path, publication['masterPath'])
    master_bytes = master.read_bytes()
    if shared.digest(master_bytes) != publication['masterSha256']:
        raise ValueError('Master continent digest does not match the exported publication')
    profile = server / 'config/eloria'
    manifest_path = profile / 'client_content_manifest.json'
    manifest = read_json(manifest_path)
    previous = manifest.get('continentGeography', {}).get('regions', {})
    current = manifest.get(STATE, {})
    publication_hash = shared.digest(raw)
    repeated = current.get('publicationSha256') == publication_hash
    if current and not repeated and publication.get('sourcePublicationSha256') != current.get('publicationSha256'):
        raise ValueError('A revised export must name sourcePublicationSha256 and map from the currently published coordinates')
    specs = copy.deepcopy(publication['regions'])
    if set(specs) != set(previous):
        raise ValueError('This release must retain all twelve existing exterior identities; identity changes require an explicit migration')
    before, pending = {publication_path: raw, master: master_bytes}, {}
    worlds, blobs, world_paths = {}, {}, {}

    def read(path):
        payload = path.read_bytes()
        before.setdefault(path, payload)
        return payload

    def stage(path, payload):
        old = read(path) if path.exists() else None
        before.setdefault(path, old)
        if old != payload:
            pending[path] = payload

    read(manifest_path)
    if not repeated:
        for filename, expected in publication.get('sourceProfileSha256', {}).items():
            path = (profile / filename).resolve()
            if not path.is_relative_to(profile.resolve()) or not path.is_file():
                raise ValueError(f'Invalid source profile fingerprint path: {filename}')
            if shared.digest(read(path)) != expected:
                raise ValueError(f'{filename}: source profile changed after continent export')
        for relative,expected in publication.get('sourceCodeSha256',{}).items():
            path=(server/relative).resolve()
            if not path.is_relative_to(server) or not path.is_file():
                raise ValueError(f'Invalid source code fingerprint path: {relative}')
            if shared.digest(read(path))!=expected:
                raise ValueError(f'{relative}: gameplay source changed after continent export')
    for region, spec in specs.items():
        validate_spec(region, spec, None if repeated else previous.get(region))
        world_path = resolve_input(client, publication_path, spec['worldManifestPath'])
        collision_path = resolve_input(client, publication_path, spec['collisionPath'])
        world, collision = json.loads(read(world_path)), read(collision_path)
        transform = world['coordinateTransform']
        if transform['serverOrigin'] != spec['serverOrigin'] or transform['serverCells'] != spec['serverCells']:
            raise ValueError(f'{region}: final client package and publication use different address frames')
        if not world.get('collision', {}).get('authoredSurfaceExport'):
            raise ValueError(f'{region}: shared-continent collision requires authoredSurfaceExport to prohibit legacy carving')
        if world['collision'].get('gridAlignment') != 'tile-centres-v1':
            raise ValueError(f'{region}: shared-continent collision requires explicit tile-centres-v1 alignment')
        worlds[region], blobs[region], world_paths[region] = world, collision, world_path

    texts, records = {}, {}
    # Establish exact shared-point mappings before rewriting portals or quests.
    for filename in CONTENT:
        path = profile / filename
        texts[filename], records[filename] = rewrite_content(read(path).decode('utf-8'), filename, specs, repeated)
    mappings = {region: {'delta': [0, 0], '_native_mapper':
                        (lambda point: list(point)) if repeated else (lambda point, spec=spec: transform_tile(point, spec))}
                for region, spec in specs.items()}
    for filename, rules in shared.RULES.items():
        if filename in texts:
            continue
        path = profile / filename
        texts[filename], _ = shared.rewrite_profile(read(path).decode('utf-8'), rules, mappings)
    texts['maps.txt'], portal_entries = replace_crossings(texts['maps.txt'], publication['connections'], specs)
    checked = validate_standing_points(specs, blobs, texts, portal_entries)
    for filename, text in texts.items():
        stage(profile / filename, text.encode('utf-8'))
    definitions = [*profile.glob('instances/*.def'), *profile.glob('spawn_groups/**/*.def'), profile / 'questlines.txt']
    for path in sorted(definitions):
        if path.exists():
            text, _ = shared.rewrite_definition(read(path).decode('utf-8'), mappings)
            stage(path, text.encode('utf-8'))
    for relative, kind in (('tools/generate_nymara_maps.py', 'generator'), ('eloria/map_layout.py', 'layout'),
                           ('eloria/world.py', 'world'), ('eloria/walkthrough.py', 'walkthrough'),
                           ('eloria/pk.py', 'pk'), ('eloria/daily_quests.py', 'daily')):
        path = server / relative
        text = read(path).decode('utf-8')
        if kind in ('generator', 'layout'):
            text = rewrite_exact_arrivals(text, kind, specs)
        else:
            text = rewrite_gameplay_source(text, kind, mappings)
        stage(path, text.encode('utf-8'))

    registry_path = client / 'godot-client/data/maps/registry.json'
    registry = json.loads(read(registry_path))
    for region, spec in specs.items():
        if region not in registry['maps']:
            raise ValueError(f'{region}: missing existing client registry identity')
        entry = registry['maps'][region]
        entry.update(coordinateTransform=copy.deepcopy(worlds[region]['coordinateTransform']), landscapeTransitions=True,
                     continentGeography={'translation': spec['translation'], 'geometryMode': 'continent-chunks-v1'})
    stage(registry_path, shared.json_bytes(registry))
    # Room-local positions stay local. Only metadata naming an exterior target
    # follows the continent deformation, including gauntlet completion returns.
    seen_paths = set(world_paths.values())
    for entry in registry['maps'].values():
        if not entry.get('manifest'):
            continue
        path = (client / 'godot-client' / entry['manifest'].removeprefix('res://')).resolve()
        if path in seen_paths:
            continue
        seen_paths.add(path)
        if not path.is_relative_to(client) or not path.is_file():
            raise ValueError(f'Registry manifest is missing or outside client: {path}')
        data = json.loads(read(path))
        updated = remap_metadata(data, specs, mappings)
        if updated != data:
            stage(path, shared.json_bytes(updated))

    for index, entry in enumerate(manifest.get('maps', [])):
        region = entry['id']
        manifest['maps'][index] = remap_metadata(entry, specs, mappings, region)
        if region in specs:
            spec = specs[region]
            manifest['maps'][index].update(arrival=spec['arrival'], server_cells=spec['serverCells'][0],
                                           server_origin=spec['serverOrigin'],
                                           coordinateTransform=copy.deepcopy(worlds[region]['coordinateTransform']))
    for key, value in list(manifest.items()):
        if key in ('maps', STATE, 'continentGeography'):
            continue
        region = next((region for region in sorted(specs, key=len, reverse=True)
                       if key.startswith(region + '_') or region == 'sunmane_steppe' and key in ('sunmane_npcs', 'sunmane_resources')), None)
        manifest[key] = remap_metadata(value, specs, mappings, region)
    # Derive every manifest portal from the final authoritative table.
    all_portals = {}
    for line in texts['maps.txt'].splitlines():
        fields = [field.strip() for field in line.split('|')]
        if len(fields) in (7, 8) and fields[0] == 'portal':
            start = 2 if len(fields) == 7 else 3
            all_portals.setdefault(fields[1], []).append({'server_tile': [int(fields[start]), int(fields[start + 1])],
                                                         'destination': fields[start + 2]})
    for entry in manifest.get('maps', []):
        entry['portals'] = all_portals.get(entry['id'], [])
    runtime = runtime_specs(specs, previous)
    manifest['continentGeography'] = {'schema': 1, 'geometryMode': 'continent-chunks-v1',
        'geographySha256': publication_hash, 'masterSha256': publication['masterSha256'], 'regions': runtime}
    placements = (copy.deepcopy(current['placements']) if repeated and 'placements' in current
                  else placement_contracts(specs))
    manifest[STATE] = {'schema': 1, 'revision': publication['revision'], 'publicationSha256': publication_hash,
                      'masterSha256': publication['masterSha256'], 'placements': placements, 'collisionSha256':
                      {region: shared.digest(blob) for region, blob in blobs.items()}}
    stage(manifest_path, shared.json_bytes(manifest))
    stage(server / 'eloria/continent_geography.py', shared.runtime_migration_source(runtime).encode('utf-8'))
    database_path = server / 'eloria/database.py'
    stage(database_path, shared.install_geography_hook(read(database_path).decode('utf-8')).encode('utf-8'))
    graph, streaming = connection_manifests(publication, worlds, specs)
    stage(client / 'eloria-assets/maps/nymara-regions/region-connections.json', shared.json_bytes(graph))
    stage(client / 'godot-client/data/maps/exterior_connections.json', shared.json_bytes(streaming))
    stage(profile / 'exterior_connections.json', shared.json_bytes(streaming))
    report = {'schema': 1, 'revision': publication['revision'], 'publicationSha256': publication_hash,
              'repeatedPublication': repeated, 'masterSha256': publication['masterSha256'],
              'territories': len(specs), 'connections': len(publication['connections']),
              'exteriorPortalLanes': len(portal_entries), 'verifiedStandingPoints': checked,
              'contentRecords': records, 'files': [{'path': str(path),
                  'beforeSha256': shared.digest(before[path]) if before[path] is not None else None,
                  'afterSha256': shared.digest(payload)} for path, payload in pending.items()]}
    return before, pending, report


def build_contracts(client, server, publication_path, data):
    if int(os.environ.get('ELORIA_BUILD_CORES', '999')) > 8:
        raise ValueError('Run --build through run_limited.py to enforce the eight-core ceiling')
    publication = read_json(publication_path)
    def run(cwd, script, *arguments):
        subprocess.run([sys.executable, '-u', str(script), *map(str, arguments)], cwd=cwd, check=True)
    for region in publication['regions']:
        run(server, server / 'tools/sync_authored_collision.py', '--client', client / 'eloria-assets/maps', '--region', region)
    run(server, server / 'tools/generate_nymara_maps.py', data)
    run(server, server / 'tools/generate_nymara_invasion_spawns.py')
    run(client, client / 'eloria-assets/tools/sync_package_content.py', '--manifest',
        server / 'config/eloria/client_content_manifest.json', '--digests', '--apply')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client', type=Path, default=CLIENT)
    parser.add_argument('--server', type=Path, required=True)
    parser.add_argument('--publication', type=Path, default=PUBLICATION)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--data', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    if args.build and (not args.apply or args.data is None):
        parser.error('--build requires --apply and --data')
    before, pending, report = plan(args.client, args.server, args.publication)
    if args.apply:
        shared.apply_plan(before, pending)
    if args.build:
        build_contracts(args.client.resolve(), args.server.resolve(), args.publication.resolve(), args.data.resolve())
    report.update(applied=args.apply, built=args.build)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_bytes(shared.json_bytes(report))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
