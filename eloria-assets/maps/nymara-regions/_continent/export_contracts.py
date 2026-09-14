"""Seat authoritative content on the exported continent's actual walking grid.

This is an export stage, not a profile editor. It freezes the input profile,
folds all four half-metre samples exactly as the server does, and emits explicit
old-to-new standing points. A disconnected doorway or road is a geometry error:
the diagnostic is written, and no publication is emitted to conceal it.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import importlib
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
import time

import numpy as np

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[2] / 'tools'
REVISION = 'diagonal-spine-v1'
GAMEPLAY_SOURCES = ('eloria/daily_quests.py', 'eloria/world.py', 'eloria/walkthrough.py', 'eloria/pk.py')
# The coordinated build regenerates these from the served profile after the
# plan is applied; a re-run accepts only their exact deterministic regeneration.
BUILD_REGENERATED = ('config/eloria/spawn_groups/invasion/invasion_nymara.def',)


def write_json(path, value):
    def clean(item):
        if isinstance(item, np.ndarray):
            return item.tolist()
        if isinstance(item, np.generic):
            return item.item()
        raise TypeError(type(item).__name__)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, default=clean) + '\n', encoding='utf-8', newline='\n')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def terrain_revision(spec, collision, server_grid):
    """Content-address saved standing space independently for each territory.

    The release label is a schema identity, not a terrain identity. Reusing it
    after moving a cliff or building must not strand an existing character.
    Baseline/current-source bookkeeping is excluded so a repeated export keeps
    the same migration marker, including after its first profile publication.
    """
    geometry = collision['collision']
    identity = {'schema': 1, 'release': REVISION,
        'geometrySha256': geometry['sourceGlbSha256'],
        'collisionSha256': sha(spec['collisionPath']),
        'heightEncoding': geometry['heightEncoding'],
        'serverGridSha256': hashlib.sha256(np.ascontiguousarray(server_grid, dtype=np.uint8).tobytes()).hexdigest(),
        **{field: spec[field] for field in ('serverOrigin', 'serverCells', 'translation', 'arrival', 'contentPositions')}}
    encoded = json.dumps(identity, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    return REVISION + ':' + hashlib.sha256(encoded).hexdigest()


def revision_metadata(path, manifest, spec, master_sha):
    """Prepare consistent territory/chunk metadata, without writing any files."""
    manifest['terrainRevision'] = spec['terrainRevision']
    manifest['continentPublication'] = {'revision': REVISION, 'masterSha256': master_sha,
        'collisionSha256': sha(Path(spec['collisionPath'])), 'terrainRevision': spec['terrainRevision']}
    children = []
    if 'streamingChunks' in manifest:
        manifest['streamingChunks']['terrainRevision'] = spec['terrainRevision']
        folder = Path(path).parent.resolve()
        for entry in manifest['streamingChunks']['chunks']:
            child_path = (folder / entry['manifest']).resolve()
            if not child_path.is_relative_to(folder):
                raise ValueError(f'{child_path}: chunk revision metadata must remain inside its named territory')
            child = json.loads(child_path.read_text(encoding='utf-8'))
            child['terrainRevision'] = spec['terrainRevision']
            child['continentPublication'] = copy.deepcopy(manifest['continentPublication'])
            # The territory frame is final only after contracts (arrival walking
            # height); every independent cell must carry the identical frame.
            child['coordinateTransform'] = copy.deepcopy(manifest['coordinateTransform'])
            children.append((child_path, child))
    return children


def frozen_profile(server, shared, baseline=None):
    """Freeze the original authored frame before any coordinated publication."""
    baseline = Path(baseline or HERE / 'legacy-server-profile')
    certificate_path = baseline / 'snapshot.json'
    current_manifest = json.loads((server / 'config/eloria/client_content_manifest.json').read_text(encoding='utf-8'))
    if not certificate_path.exists():
        if current_manifest.get('diagonalContinent'):
            raise ValueError('Server already uses diagonal coordinates, but immutable legacy-server-profile is missing; restore the original snapshot before re-exporting')
        profile = server / 'config/eloria'
        paths = {profile / name for name in (*shared.RULES, 'client_content_manifest.json', 'creatures.txt')}
        paths.update(profile.glob('instances/*.def'))
        paths.update(profile.glob('spawn_groups/**/*.def'))
        paths.add(profile / 'questlines.txt')
        paths.update(server / relative for relative in GAMEPLAY_SOURCES)
        files = {}
        for source in sorted(path for path in paths if path.exists()):
            relative = source.relative_to(server).as_posix()
            target = baseline / relative
            payload = source.read_bytes()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            files[relative] = hashlib.sha256(payload).hexdigest()
        write_json(certificate_path, {'schema': 1, 'purpose': 'Immutable pre-diagonal authored coordinate profile', 'files': files})
    certificate = json.loads(certificate_path.read_text(encoding='utf-8'))
    for relative, expected in certificate['files'].items():
        if not (baseline / relative).exists() or sha(baseline / relative) != expected:
            raise ValueError(f'Immutable baseline changed: {relative}; restore its certified original bytes')
    return baseline, certificate, current_manifest


def previous_release(current, history=None):
    published = current.get('diagonalContinent', {}).get('publicationSha256')
    if not published:
        return None
    path = Path(history or HERE / 'publication-history') / (published + '.json')
    if not path.exists() or sha(path) != published:
        raise ValueError(f'Published diagonal coordinates require their exact publication history {published}; cannot safely deform current coordinates without it')
    previous = json.loads(path.read_text(encoding='utf-8'))
    if any('baselineTilePositions' not in spec for spec in previous['regions'].values()):
        raise ValueError('Previous publication lacks baseline point history; restore an audited publication before re-exporting')
    return previous


def freeze_return_targets(baseline, publisher):
    """Snapshot exterior targets declared by rooms, before their manifests move."""
    path = baseline / 'interior-return-targets.json'
    if path.exists():
        data = json.loads(path.read_text(encoding='utf-8'))
        return data['targets']
    current = json.loads((baseline / 'config/eloria/client_content_manifest.json').read_text(encoding='utf-8'))
    specs = {r: {'serverOrigin': v['serverOrigin'], 'previousServerOrigin': v['serverOrigin']}
             for r, v in current['continentGeography']['regions'].items()}
    client = TOOLS.parents[1]
    registry = json.loads((client / 'godot-client/data/maps/registry.json').read_text(encoding='utf-8'))
    targets, files = [], {}
    context = {'file': ''}
    def record(region, point):
        targets.append({'region': region, 'oldTile': list(point), 'source': context['file']})
        return list(point)
    mappings = {r: {'delta': [0, 0], '_native_mapper': lambda point, r=r: record(r, point)} for r in specs}
    for region, entry in registry['maps'].items():
        if region in specs or not entry.get('manifest'):
            continue
        source = (client / 'godot-client' / entry['manifest'].removeprefix('res://')).resolve()
        if not source.is_relative_to(client) or not source.exists():
            raise ValueError(f'Missing interior source manifest {source}')
        context['file'] = source.relative_to(client).as_posix()
        files[context['file']] = sha(source)
        publisher.remap_metadata(json.loads(source.read_text(encoding='utf-8')), specs, mappings)
    unique = {(v['region'], *v['oldTile'], v['source']): v for v in targets}
    data = {'schema': 1, 'sourceManifestSha256': files, 'targets': list(unique.values())}
    write_json(path, data)
    return data['targets']


def verify_current_profile(server, baseline, certificate, previous, shared, publisher):
    """Reject content edits that an old snapshot would silently overwrite."""
    if previous is None:
        for relative, expected in certificate['files'].items():
            if not (server / relative).exists() or sha(server / relative) != expected:
                raise ValueError(f'{relative}: current server differs from immutable pre-publication baseline')
        return
    specs = copy.deepcopy(previous['regions'])
    # Reconstruct the currently served coordinates from the immutable frame.
    for region, spec in specs.items():
        spec['tilePositions'] = copy.deepcopy(spec['baselineTilePositions'])
        spec['previousServerOrigin'] = spec['baselineServerOrigin']
        spec['contentTransform'] = spec['baselineContentTransform']
        spec['removedInteractiveIds'] = spec['baselineRemovedInteractiveIds']
    mappings = {r: {'delta': [0, 0], '_native_mapper': lambda old, spec=spec: publisher.transform_tile(old, spec)} for r, spec in specs.items()}
    regenerated = []
    for relative, expected in certificate['files'].items():
        path = server / relative
        if not path.exists():
            raise ValueError(f'{relative}: authoritative source disappeared after the preceding publication')
        old_text = (baseline / relative).read_text(encoding='utf-8')
        name = Path(relative).name
        if name == 'client_content_manifest.json':
            continue  # Digests and generated package metadata legitimately change at publication.
        if name in publisher.CONTENT:
            text, _ = publisher.rewrite_content(old_text, name, specs, False)
        elif name in shared.RULES:
            text, _ = shared.rewrite_profile(old_text, shared.RULES[name], mappings)
            if name == 'maps.txt':
                text, _ = publisher.replace_crossings(text, previous['connections'], specs)
        elif name.endswith('.def') or name == 'questlines.txt':
            text, _ = shared.rewrite_definition(old_text, mappings)
        elif relative in GAMEPLAY_SOURCES:
            kind = {'daily_quests.py': 'daily', 'world.py': 'world', 'walkthrough.py': 'walkthrough', 'pk.py': 'pk'}[name]
            text = publisher.rewrite_gameplay_source(old_text, kind, mappings)
        else:
            text = old_text
        if path.read_text(encoding='utf-8') != text:
            if relative in BUILD_REGENERATED:
                regenerated.append(relative)
                continue
            raise ValueError(f'{relative}: server content changed beyond the previous coordinated publication; reconcile the immutable baseline explicitly')
    if regenerated:
        result = subprocess.run([sys.executable, str(server / 'tools/generate_nymara_invasion_spawns.py'), '--check'],
                                cwd=server, capture_output=True, text=True)
        if result.returncode != 0:
            raise ValueError('Build-regenerated content differs from its deterministic regeneration: ' + ', '.join(regenerated)
                             + ' ' + (result.stdout + result.stderr)[-1500:].strip())


def rebase_publication(publication, previous):
    """Keep geometry in its original frame, publish remaps from today's frame."""
    for region, spec in publication['regions'].items():
        baseline = copy.deepcopy(spec['tilePositions'])
        spec['baselineTilePositions'] = baseline
        spec['baselineServerOrigin'] = list(spec['previousServerOrigin'])
        spec['baselineContentTransform'] = copy.deepcopy(spec['contentTransform'])
        spec['baselineRemovedInteractiveIds'] = list(spec['removedInteractiveIds'])
        if previous is None:
            continue
        prior = previous['regions'][region]
        old_baseline = prior['baselineTilePositions']
        mapping = {}
        for old_key, target in baseline.items():
            current = old_baseline.get(old_key)
            if current is None:
                # A newly required semantic point has no proven current address.
                raise ValueError(f'{region}:{old_key}: revised contract has no source in the currently published baseline table')
            current_key = key(current)
            if current_key in mapping and mapping[current_key] != target:
                raise ValueError(f'{region}:{current_key}: distinct original points collapsed in the previous publication but need different revised targets')
            mapping[current_key] = target
        spec['tilePositions'] = mapping
        for portal in spec['portalPositions'].values():
            portal['oldTile'] = list(old_baseline[key(portal['oldTile'])])
        spec['previousServerOrigin'] = list(prior['serverOrigin'])
        # All semantic points are explicit. The continuous fallback is identity
        # in the previous local frame; changed geographic rectangles are also
        # recorded explicitly before reaching this stage.
        spec['contentTransform'] = {'scale': 1., 'sourceCenter': [0, 0], 'targetCenter': [0, 0]}
        spec['removedInteractiveIds'] = []  # These IDs were removed by the first release.


def key(point):
    return f'{int(point[0])}:{int(point[1])}'


def rows(text):
    for number, line in enumerate(text.splitlines(), 1):
        if line.strip() and not line.lstrip().startswith('#'):
            yield number, [field.strip() for field in line.split('|')]


def server_modules(server):
    """Use the selected paired server's actual stage and footprint contracts."""
    server = Path(server).resolve()
    for directory in (server, server / 'tools', TOOLS):
        if str(directory) not in sys.path:
            sys.path.insert(0, str(directory))
    result = {}
    for name in ('collision_sources', 'sync_authored_collision', 'eloria.creatures',
                 'eloria.footprint', 'publish_continent_geography', 'publish_diagonal_continent'):
        module = importlib.import_module(name)
        if name.startswith('eloria.') or name in ('collision_sources', 'sync_authored_collision'):
            if not Path(module.__file__).resolve().is_relative_to(server):
                raise ValueError(f'{name} was loaded from a different server checkout')
        result[name] = module
    return result


def fold_server_grid(result, sources, sync):
    """Four subcells, maximum floor, zero if any part of an actor tile is blocked."""
    grid = np.asarray(result['grid'], dtype=np.uint8)
    height, width = grid.shape
    if height % 2 or width % 2 or height != width:
        raise ValueError('Named territory collision must have a square even half-cell envelope')
    blocks = grid.reshape(height // 2, 2, width // 2, 2)
    folded = blocks.max(axis=(1, 3))
    folded[~blocks.all(axis=(1, 3))] = 0
    encoding = result['collision']['heightEncoding']
    transform = sources.GridTransform(cell_tiles=.5, shift=0,
        metres_per_unit=encoding['step'], height_origin=encoding['origin'])
    quantised = sources.requantise(folded, transform)
    factor, largest, detail = sync.choose_stage(quantised)
    return sync.rescale(quantised, factor), factor, largest, detail


def collision_world_digest(world):
    """Include every shared field used by exact collision, excluding content posts."""
    digest = hashlib.sha256()
    for name, value in (('height', world.height), ('owner', world.owner),
                        ('water-mask', world.water['mask']), ('water-surface', world.water['surface'])):
        array = np.ascontiguousarray(value)
        digest.update(name.encode()); digest.update(str((array.shape, array.dtype.str)).encode())
        digest.update(memoryview(array).cast('B'))
    digest.update(json.dumps({'bounds': [world.x0, world.z0, world.x1, world.z1],
        'cell': getattr(world, 'cell', 2.), 'ids': world.ids,
        'waterPlan': {name: getattr(world, 'plan', {}).get(name) for name in ('sea_level', 'rivers', 'lakes')}}, sort_keys=True).encode())
    return digest.hexdigest()


def cached_collision(world, region, manifest, glb_path, collision_path, output, world_digest):
    """Keep expensive completed rasters after a later placement failure."""
    import collision_export as exporter
    signature = {'schema': 1, 'worldSha256': world_digest, 'region': region, 'glbSha256': sha(glb_path),
        'address': world.address(region), 'center': world.regions[region]['center'],
        'collisionRoots': sorted(manifest.get('collision', {}).get('nodeNames', [])),
        'surfacePrefixes': manifest.get('navigation', {}).get('surfaceNodePrefixes', ['Terrain_', 'Walk_']),
        'connections': [c for c in world.connections if region in c.get('regions', [])],
        'sources': {name: sha(HERE / name) for name in ('collision_export.py', 'world_layout.py', 'terrain_export.py', 'landscape.py')},
        'readerSha256': sha(Path(exporter.GR.__file__))}
    signature_text = json.dumps(signature, sort_keys=True, default=lambda a: np.asarray(a).tolist())
    signature_hash = hashlib.sha256(signature_text.encode()).hexdigest()
    folder = output / 'collision-cache'; folder.mkdir(exist_ok=True)
    metadata_path, array_path = folder / (region + '.json'), folder / (region + '.npz')
    if metadata_path.exists() and array_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
        if metadata.get('inputSha256') == signature_hash and metadata.get('arraysSha256') == sha(array_path):
            with np.load(array_path, allow_pickle=False) as arrays:
                result = {'collision': metadata['collision'], 'grid': arrays['grid'],
                          'heights': arrays['heights'], 'walkable': arrays['walkable']}
            grid = result['grid']; height, width = grid.shape
            collision_path.write_bytes(struct.pack('<4sHHII', b'EWCG', 2, 0, width, height) + grid.tobytes())
            print(f'{region}: reused certified collision raster', flush=True)
            return result
    result = exporter.export_collision(world, region, manifest, glb_path, collision_path)
    np.savez(array_path, grid=result['grid'], heights=result['heights'], walkable=result['walkable'])
    write_json(metadata_path, {'inputSha256': signature_hash, 'inputs': signature,
        'arraysSha256': sha(array_path), 'collision': result['collision']})
    return result


class PlacementError(ValueError):
    pass


class RegionPlacement:
    """Deterministic bounded searches on one hub-connected server component."""
    def __init__(self, world, content, region, spec, collision, grid, sources, report):
        self.world, self.content, self.region, self.spec = world, content, region, spec
        self.collision, self.grid, self.sources = collision, grid.copy(), sources
        self.report = report
        self.records, self.failures = report['placements'], report['failures']
        self.reserved = np.zeros(grid.shape, dtype=bool)
        self.reachable = grid != 0
        self.storage = set()
        self.bodies = set()
        self.fixed = set()
        self.actor_tiles = set()
        self.old_entries = {}
        self.entry_by_identity = {}
        self._index_metadata(content.templates[region])

    def _index_metadata(self, value):
        if isinstance(value, list):
            for entry in value:
                self._index_metadata(entry)
        elif isinstance(value, dict):
            point = value.get('serverTile', value.get('server_tile'))
            if point is not None:
                self.old_entries.setdefault(key(point), []).append(value)
            for name in ('id', 'name'):
                if name in value:
                    self.entry_by_identity.setdefault(str(value[name]).casefold(), value)
            for entry in value.values():
                if isinstance(entry, (dict, list)):
                    self._index_metadata(entry)

    def expected(self, old, identity=None):
        origin = self.spec['previousServerOrigin']
        point = [old[0] + .5 - origin[0], 0., origin[1] - old[1] - .5]
        entry = self.entry_by_identity.get(str(identity).casefold()) if identity else None
        if entry is None:
            entries = self.old_entries.get(key(old), [])
            entry = next((e for e in entries if e.get('doorNode') or e.get('node')), entries[0] if entries else {})
        # Server coordinates are authoritative. A linked architectural root
        # determines displacement, but stale marker coordinates cannot move it.
        authored = (getattr(self.content, 'authored_actor_points', {}).get((self.region, identity))
                    if identity else None)
        if authored is None:
            authored = getattr(self.content, 'authored_server_points', {}).get((self.region, tuple(old)))
        if authored is not None:
            # Deliberately relocated doors and their separate return squares
            # have exact authored global coordinates. Both must use the same
            # override already consumed by Content.mapped_server_point.
            p = np.asarray(authored, float)
            if p.shape != (3,) or not np.isfinite(p).all():
                raise ValueError(f'{self.region}:{key(old)}: invalid authored semantic position')
        else:
            p = self.content.mapped_point(self.region, point,
                entry.get('node', entry.get('doorNode')), entry.get('landmark'))
        center = self.world.regions[self.region]['center']
        return np.array([p[0] - center[0] + self.spec['serverOrigin'][0] - .5,
                         self.spec['serverOrigin'][1] - (p[2] - center[1]) - .5])

    def in_grid(self, tile):
        return 0 <= tile[0] < self.grid.shape[1] and 0 <= tile[1] < self.grid.shape[0]

    def valid(self, tile, shape=(1, 1), allow_reserved=False, mask=None):
        width, depth = shape
        x0, y0 = tile[0] - (width - 1) // 2, tile[1] - (depth - 1) // 2
        x1, y1 = x0 + width, y0 + depth
        if x0 < 0 or y0 < 0 or x1 > self.grid.shape[1] or y1 > self.grid.shape[0]:
            return False
        ground = self.reachable if mask is None else mask
        return bool(ground[y0:y1, x0:x1].all() and
                    (allow_reserved or not self.reserved[y0:y1, x0:x1].any()))

    def reserve(self, tile, shape=(1, 1), margin=0):
        width, depth = shape
        x0 = max(0, tile[0] - (width - 1) // 2 - margin)
        y0 = max(0, tile[1] - (depth - 1) // 2 - margin)
        self.reserved[y0:min(self.grid.shape[0], y0 + depth + 2 * margin),
                      x0:min(self.grid.shape[1], x0 + width + 2 * margin)] = True

    def failure(self, label, old, expected, radius, reason):
        origin = self.spec['serverOrigin']
        center = self.world.regions[self.region]['center']
        self.failures.append({'region': self.region, 'record': label, 'oldTile': old,
            'expectedTile': np.round(expected, 3).tolist(),
            'expectedGlobalXZ': [round(float(expected[0] + .5 - origin[0] + center[0]), 3),
                                 round(float(origin[1] - expected[1] - .5 + center[1]), 3)],
            'maximumDisplacementMetres': radius, 'reason': reason})

    def nearest(self, expected, radius, shape=(1, 1), allow_reserved=False, mask=None):
        x, y = expected
        x0, x1 = max(0, math.ceil(x - radius)), min(self.grid.shape[1], math.floor(x + radius) + 1)
        y0, y1 = max(0, math.ceil(y - radius)), min(self.grid.shape[0], math.floor(y + radius) + 1)
        if x0 >= x1 or y0 >= y1:
            return None
        ground = self.reachable if mask is None else mask
        ys, xs = np.nonzero(ground[y0:y1, x0:x1])
        xs, ys = xs + x0, ys + y0
        distance = (xs - x) ** 2 + (ys - y) ** 2
        # Stable y/x tie-breaking makes byte-identical source produce byte-identical output.
        for i in np.argsort(distance, kind='stable'):
            if distance[i] > radius ** 2 + 1e-8:
                break
            tile = (int(xs[i]), int(ys[i]))
            if self.valid(tile, shape, allow_reserved, mask):
                return list(tile)
        return None

    def place_body(self, expected, radius, shape, label):
        """Nearest standing point whose static body seals no ground beyond its footprint.

        The live server routes every walker around the tiles an actor stands
        on, so a body in a one-tile mouth would cut a whole pocket of placed
        or later content off the inhabited arrival. Ground behind an accepted
        body is likewise withdrawn from every later placement.
        """
        width, depth = shape
        excluded = np.zeros(self.grid.shape, dtype=bool)
        arrival = tuple(self.spec['arrival'])
        placed = {tuple(t) for t in self.spec['tilePositions'].values()} | set(self.fixed)
        for _ in range(256):
            tile = self.nearest(expected, radius, shape, mask=self.reachable & ~excluded)
            if tile is None:
                return None
            x0, y0 = tile[0] - (width - 1) // 2, tile[1] - (depth - 1) // 2
            window = np.s_[y0:y0 + depth, x0:x0 + width]
            saved = self.grid[window].copy()
            self.grid[window] = 0
            reachable = self.sources.reachable_from(self.grid, arrival, 2)
            lost = int(self.reachable.sum()) - int(reachable.sum())
            severed = lost > width * depth + 2 or any(
                self.reachable[y, x] and not reachable[y, x] for x, y in placed if (x, y) != tuple(tile))
            if severed:
                self.grid[window] = saved
                excluded[window] = True
                self.report['regions'][self.region].setdefault('bodyRelocations', []).append(
                    {'record': label, 'rejectedTile': list(tile), 'sealedTiles': lost})
                continue
            self.reachable = reachable
            self.bodies.add(tuple(tile))
            return tile
        return None

    def place(self, old, label, radius, shape=(1, 1), reserve=False, identity=None, body=False):
        old = list(map(int, old))
        expected = self.expected(old, identity)
        existing = self.spec['tilePositions'].get(key(old))
        if existing is not None:
            # A door, its bound interactive, and a quest return must name one
            # exact point. Never emit conflicting remaps for a shared source tile.
            tile = list(existing) if self.valid(existing, shape, allow_reserved=True) else None
        elif body:
            tile = self.place_body(expected, radius, shape, label)
        else:
            tile = self.nearest(expected, radius, shape)
        if tile is None:
            self.failure(label, old, expected, radius, 'No hub-connected unoccupied standing point with the required footprint')
            return None
        displacement = float(np.linalg.norm(np.asarray(tile) - expected))
        if displacement > radius + 1e-8:
            self.failure(label, old, expected, radius, 'Shared source tile was already resolved outside this record\'s movement budget')
            return None
        self.spec['tilePositions'][key(old)] = tile
        if reserve:
            self.reserve(tile, shape)
        self.records.append({'region': self.region, 'record': label, 'oldTile': old, 'tile': tile,
            'expectedTile': np.round(expected, 3).tolist(), 'displacementMetres': round(displacement, 3),
            'maximumDisplacementMetres': radius, 'footprint': list(shape)})
        return tile

    def connect_hub(self, old_arrival, preferred=None):
        center = np.asarray(self.world.regions[self.region]['center'], dtype=float)
        hub = np.asarray(self.world.hub(self.region) if hasattr(self.world, 'hub') else center, dtype=float)
        # The inhabited arrival can differ from the geographic ownership seed.
        # Express it in the same unchanged territory-local server address.
        offset = hub - center
        expected = np.asarray(self.spec['serverOrigin'], dtype=float) + offset * [1., -1.] - .5
        arrival = self.nearest(expected, 12., mask=preferred) if preferred is not None else None
        preference = 'largest component within hub budget' if arrival is not None else 'nearest local component'
        if arrival is None:
            arrival = self.nearest(expected, 12.)
        if arrival is None:
            self.failure('safe arrival', old_arrival, expected, 12, 'No ground within 12 m of the inhabited hub')
            self.reachable[:] = False
            return
        self.spec['arrival'] = arrival
        self.spec['tilePositions'][key(old_arrival)] = arrival
        self.reachable = self.sources.reachable_from(self.grid, tuple(arrival), 2)
        self.reserve(arrival, margin=2)
        self.fixed.add(tuple(arrival))
        self.report['regions'][self.region]['hubReachableTiles'] = int(self.reachable.sum())
        self.report['regions'][self.region]['arrivalSelection'] = {
            'method': preference, 'tile': arrival, 'displacementMetres': round(float(np.linalg.norm(arrival - expected)), 3)}
        if int(self.reachable.sum()) < 64:
            self.failure('safe arrival', old_arrival, expected, 12, 'Hub component has fewer than 64 tiles')

    def check_fixed(self, tile, label):
        tile = list(map(int, tile))
        if not self.valid(tile, allow_reserved=True):
            self.failure(label, None, np.array(tile), 0, 'Exact crossing or return is not reachable from the hub')
            return False
        self.fixed.add(tuple(tile))
        self.reserve(tile, margin=1)
        return True

    def stamp_storage(self, tiles):
        for tile in tiles:
            self.storage.add(tuple(tile))
            x, y = tile
            self.grid[max(0, y - 1):y + 2, max(0, x - 1):x + 2] = 0
            self.reserve(tile, (3, 3))
        self.reachable = self.sources.reachable_from(self.grid, tuple(self.spec['arrival']), 2)
        for tile in self.fixed:
            self.check_fixed(tile, 'fixed route after storage bodies')
        for tile in tiles:
            access = self.nearest(tile, 4, allow_reserved=True)
            if access is None:
                self.failure('storage access', None, np.array(tile), 4, 'Storage has no hub-connected access within four tiles')
        self.report['regions'][self.region]['hubReachableAfterStorageTiles'] = int(self.reachable.sum())

    def local_position(self, tile):
        x, y = tile
        floor = float(np.mean(self.collision['heights'][y * 2:y * 2 + 2, x * 2:x * 2 + 2]))
        return [x + .5 - self.spec['serverOrigin'][0], floor,
                self.spec['serverOrigin'][1] - y - .5]


def content_rows(profile_text, ids, publisher):
    records = {group: {r: [] for r in ids} for group in ('npcs', 'harvest', 'spawns', 'interactives')}
    for filename, (keyword, mi, xi, yi, group, identity_index) in publisher.CONTENT.items():
        counts = {}
        for number, fields in rows(profile_text[filename]):
            if len(fields) <= max(mi, xi, yi) or fields[mi] not in ids or keyword and fields[0] != keyword:
                continue
            region = fields[mi]
            ordinal = counts.get(region, 0)
            counts[region] = ordinal + 1
            identity = str(ordinal) if identity_index is None else fields[identity_index]
            records[group][region].append({'id': identity, 'old': [int(fields[xi]), int(fields[yi])],
                'fields': fields, 'label': f'{filename}:{number}:{identity}'})
    return records


def place_doors(text, placements, connections):
    ids = set(placements)
    old_departures = {r: set() for r in ids}
    # Reserve automatic thresholds first: a room return must never be seated on
    # an unrelated road trigger and immediately transfer the player again.
    for connection in connections:
        for end in connection['ends']:
            p = placements[end['region']]
            for index, lane in enumerate(end.get('lanes', [end])):
                p.check_fixed(lane['tile'], f'{connection["id"]}:departure:{index}')
                p.check_fixed(lane['arrival'], f'{connection["id"]}:arrival:{index}')
    for number, fields in rows(text):
        if fields[0] != 'portal' or len(fields) not in (7, 8):
            continue
        start = 2 if len(fields) == 7 else 3
        source, target = fields[1], fields[start + 2]
        point, arrival = list(map(int, fields[start:start + 2])), list(map(int, fields[start + 3:start + 5]))
        if source in ids and target in ids:
            old_departures[source].add(tuple(point))
            continue
        for region, old, direction in ((source, point, 'door'), (target, arrival, 'return')):
            if region not in ids:
                continue
            p = placements[region]
            tile = p.place(old, f'maps.txt:{number}:{direction}:{source}->{target}', 5)
            if tile is not None:
                portal_id = next((str(e['id']) for e in p.old_entries.get(key(old), []) if 'id' in e and
                    any(k in e for k in ('destinationMap', 'targetMap'))), f'profile-{number}-{direction}')
                p.spec['portalPositions'][portal_id] = {'oldTile': old, 'tile': tile}
                p.fixed.add(tuple(tile))
                p.reserve(tile)
    return old_departures


def collect_gameplay_points(server, profile_text, placements, records, shared, publisher):
    """Exercise publication's own readers, so no supported source coordinate is omitted."""
    current = {'label': '', 'radius': 12., 'area': False}
    def remap(region, old):
        p = placements[region]
        if key(old) in p.spec['tilePositions']:
            return p.spec['tilePositions'][key(old)]
        if current['area']:
            # Region rectangles are bounds, not standing points; preserve their
            # shape by using the continuous transform without snapping to a path.
            point = publisher.transform_tile(old, p.spec)
            p.spec['tilePositions'][key(old)] = point
            return point
        tile = p.place(old, current['label'], current['radius'])
        return tile if tile is not None else list(map(int, np.rint(p.expected(old))))
    mappings = {r: {'delta': [0, 0], '_native_mapper': lambda old, r=r: remap(r, old)} for r in placements}
    # Bind daily objectives to the retained authoritative resource or recipient.
    daily_path = server / 'eloria/daily_quests.py'
    if daily_path.exists():
        for node in ast.walk(ast.parse(daily_path.read_text(encoding='utf-8'))):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != 'DailyTask' or len(node.args) < 7:
                continue
            values = [ast.literal_eval(v) for v in node.args[:7]]
            recipient, kind_, resource, _, region, x, y = values
            if region not in placements or kind_ == 'kill':
                continue
            p = placements[region]
            if key((x, y)) in p.spec['tilePositions']:
                continue
            if kind_ == 'harvest':
                candidates = [v for v in records['harvest'][region] if v['fields'][5] == resource and
                              math.dist(v['old'], (x, y)) <= 8.01]
                candidates.sort(key=lambda v: (math.dist(v['old'], (x, y)), v['id']))
                target = p.spec['contentPositions']['harvest'].get(candidates[0]['id']) if candidates else None
            else:
                target = p.spec['contentPositions']['npcs'].get(recipient)
            if target is not None:
                p.spec['tilePositions'][key((x, y))] = list(target)
                p.records.append({'region': region, 'record': f'daily:{kind_}:{resource}',
                    'oldTile': [x, y], 'tile': list(target), 'binding': 'retained resource' if kind_ == 'harvest' else 'retained recipient'})
            else:
                p.failure(f'daily:{kind_}:{resource}', [x, y], p.expected((x, y)), 8,
                          'No retained daily resource within the old completion radius, or recipient missing')
    for filename in ('territories.txt', 'special_areas.txt'):
        if filename in profile_text:
            current.update(label=filename, radius=35., area=filename == 'special_areas.txt')
            shared.rewrite_profile(profile_text[filename], shared.RULES[filename], mappings)
    for relative, text in profile_text.items():
        if relative.endswith('.def') or relative == 'questlines.txt':
            radius = 5. if relative.startswith('instances/') else 80. if relative.startswith('spawn_groups/') else 35.
            current.update(label=relative, radius=radius, area=False)
            shared.rewrite_definition(text, mappings)
    for relative, kind_ in (('eloria/world.py', 'world'), ('eloria/walkthrough.py', 'walkthrough'),
                             ('eloria/pk.py', 'pk'), ('eloria/daily_quests.py', 'daily')):
        path = server / relative
        if path.exists():
            current.update(label=relative, radius=12., area=kind_ == 'pk')
            publisher.rewrite_gameplay_source(path.read_text(encoding='utf-8'), kind_, mappings)
    manifest = json.loads(profile_text['client_content_manifest.json'])
    specs = {r: p.spec for r, p in placements.items()}
    for entry in manifest.get('maps', []):
        region = entry.get('id')
        if region not in placements:
            continue
        entry = copy.deepcopy(entry)
        # The final portal table is rebuilt from the new graph. Its removed
        # source triggers do not remain standing-point promises.
        entry.pop('portals', None)
        current.update(label='client_content_manifest.json:' + region, radius=12., area=False)
        publisher.remap_metadata(entry, specs, mappings, region)
    for name, value in manifest.items():
        if name in ('maps', 'continentGeography', 'diagonalContinent'):
            continue
        region = next((r for r in sorted(placements, key=len, reverse=True) if name.startswith(r + '_')
                       or r == 'sunmane_steppe' and name in ('sunmane_npcs', 'sunmane_resources')), None)
        current.update(label='client_content_manifest.json:' + name,
                       radius=35. if 'harvest' in name or 'resource' in name else 12., area=False)
        publisher.remap_metadata(value, specs, mappings, region)
    return mappings


def update_markers(placement, manifest):
    """Keep authored marker identities and room targets while seating their posts."""
    template = placement.content.templates[placement.region]
    metadata_keys = ('portals', 'harvestables', 'npcMarkers', 'interactives', 'pointsOfInterest', 'creatureSpawns', 'spawns')
    updated = 0
    for group in metadata_keys:
        originals = template.get(group, [])
        by_id = {str(v['id']): v for v in originals if isinstance(v, dict) and 'id' in v}
        for index, entry in enumerate(manifest.get(group, [])):
            if not isinstance(entry, dict):
                continue
            old_entry = by_id.get(str(entry.get('id')))
            if old_entry is None:
                continue
            old = old_entry.get('serverTile', old_entry.get('server_tile'))
            if old is None and 'position' in old_entry:
                origin = placement.spec['previousServerOrigin']
                old = [math.floor(old_entry['position'][0] + origin[0]),
                       math.floor(origin[1] - old_entry['position'][2])]
            tile = placement.spec['tilePositions'].get(key(old)) if old is not None else None
            if tile is None:
                continue
            entry['serverTile'] = list(tile)
            if 'server_tile' in entry:
                entry['server_tile'] = list(tile)
            entry['position'] = placement.local_position(tile)
            if 'arrivalPosition' in old_entry:
                origin = placement.spec['previousServerOrigin']
                v = old_entry['arrivalPosition']
                old_return = [math.floor(v[0] + origin[0]), math.floor(origin[1] - v[2])]
                return_tile = placement.spec['tilePositions'].get(key(old_return))
                if return_tile is not None:
                    entry['arrivalPosition'] = placement.local_position(return_tile)
            updated += 1
    arrival = placement.spec['arrival']
    manifest['spawnPoints'] = [{'id': 'continent-arrival', 'default': True,
                               'position': placement.local_position(arrival), 'serverTile': arrival}]
    manifest.setdefault('navigation', {})['defaultSpawn'] = 'continent-arrival'
    manifest['coordinateTransform']['walkingHeight'] = placement.local_position(arrival)[1]
    placement.report['regions'][placement.region]['updatedAuthoredMarkers'] = updated


def export_contracts(world, content, manifests, output, server_path):
    """Export exact placement/publication data; leave authoritative server files alone."""
    output, server = Path(output).resolve(), Path(server_path).resolve()
    output.mkdir(parents=True, exist_ok=True)
    exported = json.loads((output / 'export.json').read_text(encoding='utf-8'))
    if not hasattr(world, 'publication_connections'):
        raise ValueError('Survey exact crossing contracts before exporting standing points')
    modules = server_modules(server)
    sources, sync = modules['collision_sources'], modules['sync_authored_collision']
    shared, publisher = modules['publish_continent_geography'], modules['publish_diagonal_continent']
    baseline, certificate, current_manifest = frozen_profile(server, shared)
    previous = previous_release(current_manifest)
    if previous and not (baseline / 'interior-return-targets.json').exists():
        raise ValueError('Original interior return snapshot is missing after publication; do not sample already-transformed room metadata')
    interior_returns = freeze_return_targets(baseline, publisher)
    verify_current_profile(server, baseline, certificate, previous, shared, publisher)
    profile = baseline / 'config/eloria'
    relative_paths = [relative for relative in certificate['files'] if relative.startswith('config/eloria/')]
    profile_paths = [server / relative for relative in relative_paths]
    fingerprints = {relative.removeprefix('config/eloria/'): sha(server / relative) for relative in relative_paths}
    texts = {relative.removeprefix('config/eloria/'): (baseline / relative).read_text(encoding='utf-8') for relative in relative_paths}
    old_manifest = json.loads(texts['client_content_manifest.json'])
    old_maps = {v['id']: v for v in old_manifest['maps']}
    creatures = modules['eloria.creatures'].load_creatures(profile / 'creatures.txt')
    records = content_rows(texts, world.ids, publisher)
    report = {'schema': 1, 'revision': REVISION, 'placements': [], 'failures': [], 'regions': {},
        'sourceProfileSha256': fingerprints, 'sourceCodeSha256': {relative: sha(server / relative)
        for relative in GAMEPLAY_SOURCES if (server / relative).exists()}, 'baselineSha256': sha(baseline / 'snapshot.json')}
    publication = {'schema': 1, 'revision': REVISION, 'masterPath': exported['masterPath'],
        'masterSha256': exported['masterSha256'], 'sourceProfileSha256': fingerprints,
        'regions': {}, 'connections': copy.deepcopy(world.publication_connections),
        'visualConnections': copy.deepcopy(getattr(world, 'visual_connections', [])),
        'preloadDistance': 320, 'retainDistance': 420, 'maxResidentAdjacentMaps': 3,
        'baselineSha256': report['baselineSha256'], 'sourceCodeSha256': report['sourceCodeSha256']}
    previous_publication = current_manifest.get('diagonalContinent', {}).get('publicationSha256')
    if previous_publication:
        publication['sourcePublicationSha256'] = previous_publication
    placements, outputs = {}, {}
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    from collision_export import export_collision
    world_digest = None
    try:
        for region in world.ids:
            started = time.monotonic()
            manifest = copy.deepcopy(manifests[region])
            origin, cells = world.address(region)
            center = world.regions[region]['center']
            world_path = Path(exported['regions'][region]['world']).resolve()
            collision_path = world_path.parent / 'collision.bin'
            result = getattr(world, 'collision_exports', {}).get(region)
            if result is None:
                if world_digest is None:
                    world_digest = collision_world_digest(world)
                result = cached_collision(world, region, manifest,
                    world_path.parent / manifest['asset'].get('glb', 'world.glb'), collision_path, output, world_digest)
            elif not collision_path.exists():
                raise ValueError(f'{region}: cached collision requires its matching exported EWCG file')
            manifest['collision'] = copy.deepcopy(result['collision'])
            grid, factor, largest, detail = fold_server_grid(result, sources, sync)
            report['regions'][region] = {'stageFactor': factor, 'stageMetres': factor * .2,
                'walkableServerTiles': int((grid != 0).sum()), 'largestComponentTiles': int(largest.sum()), **detail}
            spec = {'serverOrigin': list(origin), 'serverCells': list(cells),
                'translation': [float(center[0]), 0, float(center[1])], 'arrival': list(origin),
                'terrainRevision': REVISION,
                'previousServerOrigin': list(content.templates[region]['coordinateTransform']['serverOrigin']),
                'contentTransform': {'scale': float(content.scales[region]),
                    'sourceCenter': np.asarray(content.source_centers[region]).tolist(), 'targetCenter': [0, 0]},
                'contentPositions': {group: {} for group in records}, 'tilePositions': {},
                'portalPositions': {}, 'removedInteractiveIds': [],
                'collisionPath': str(collision_path), 'worldManifestPath': str(world_path)}
            p = RegionPlacement(world, content, region, spec, result, grid, sources, report)
            p.connect_hub(old_maps[region]['arrival'], largest)
            placements[region], outputs[region], publication['regions'][region] = p, (world_path, manifest), spec
            print(f'{region}: exact server grid, stage {factor}, hub reaches {int(p.reachable.sum())} tiles in {time.monotonic()-started:.1f}s', flush=True)
        publisher.connection_rows(publication['connections'], publication['regions'])
        place_doors(texts['maps.txt'], placements, publication['connections'])
        chunk_metadata = []
        for region, p in placements.items():
            storage = []
            for row in records['interactives'][region]:
                fields = row['fields']
                if fields[4:6] == ['portal', 'maps.txt']:
                    p.spec['removedInteractiveIds'].append(row['id'])
                    continue
                if fields[4] != 'storage':
                    continue
                tile = p.place(row['old'], row['label'], 12., shape=(3, 3), reserve=True)
                if tile is not None:
                    p.spec['contentPositions']['interactives'][row['id']] = tile
                    storage.append(tile)
            if storage:
                p.stamp_storage(storage)
            for group in ('interactives', 'npcs', 'harvest', 'spawns'):
                for row in records[group][region]:
                    if group == 'interactives' and (row['id'] in p.spec['removedInteractiveIds'] or row['id'] in p.spec['contentPositions'][group]):
                        continue
                    shape = (1, 1)
                    if group == 'spawns':
                        species = row['fields'][2]
                        if species not in creatures:
                            raise ValueError(f'{row["label"]}: unknown authoritative creature {species}')
                        creature = creatures[species]
                        shape = (creature.footprint_width, creature.footprint_depth)
                    radius = {'interactives': 12, 'npcs': 12, 'harvest': 35, 'spawns': 80}[group]
                    tile = p.place(row['old'], row['label'], radius, shape, reserve=True,
                                   identity=row['id'] if group == 'npcs' else None, body=group == 'npcs')
                    if tile is not None:
                        p.spec['contentPositions'][group][row['id']] = tile
        collect_gameplay_points(baseline, texts, placements, records, shared, publisher)
        for target in interior_returns:
            p = placements[target['region']]
            # Return metadata may name the same point as a bound doorway.
            p.place(target['oldTile'], 'interior return:' + target['source'], 5.)
        if report['failures']:
            raise PlacementError(f'{len(report["failures"])} continent contracts need authored geometry or placement corrections; see contract-placement-report.json')
        # The frozen inputs must still be the source of every remap we emit.
        for path in profile_paths:
            if sha(path) != fingerprints[path.relative_to(server / 'config/eloria').as_posix()]:
                raise ValueError(f'{path}: profile changed during content placement')
        for region, p in placements.items():
            path, manifest = outputs[region]
            update_markers(p, manifest)
            p.spec['terrainRevision'] = terrain_revision(p.spec, p.collision, p.grid)
            report['regions'][region]['terrainRevision'] = p.spec['terrainRevision']
            chunk_metadata.extend(revision_metadata(path, manifest, p.spec, publication['masterSha256']))
            chosen = set(tuple(v) for v in p.spec['tilePositions'].values())
            chosen.update(p.fixed)
            p.spec['tileHeights'] = {key(tile): p.local_position(tile)[1] for tile in sorted(chosen)
                                    if p.in_grid(tile)}
        rebase_publication(publication, previous)
        for child_path, child in chunk_metadata:
            write_json(child_path, child)
        for region, (path, manifest) in outputs.items():
            manifests[region].clear()
            manifests[region].update(manifest)
            write_json(path, manifest)
        write_json(output / 'publication.json', publication)
        history = HERE / 'publication-history' / (sha(output / 'publication.json') + '.json')
        history.parent.mkdir(parents=True, exist_ok=True)
        history.write_bytes((output / 'publication.json').read_bytes())
        report['ready'] = True
        return publication
    finally:
        report.setdefault('ready', False)
        write_json(output / 'contract-placement-report.json', report)
