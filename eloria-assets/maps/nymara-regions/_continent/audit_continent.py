"""Read emitted master/territory/chunk geometry and verify its common surface.

This audit does not rebuild or repair maps. The only output is its JSON report.
Every actual two-metre terrain triangle must occur once in the shared source,
master, union of territories, and union of streaming chunks. Attribute checks
use the emitted source vertex buffer, including colours, normals and UVs.
"""
from __future__ import annotations

import argparse
import ast
from collections import defaultdict
import gzip
import hashlib
import inspect
import json
from pathlib import Path
import struct
import sys
import time

import numpy as np

HERE = Path(__file__).resolve().parent
CLIENT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / '_toolkit'))
import glb_reader as GR
from world_layout import triangle_sample


class AuditError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise AuditError(message)


class Inputs:
    def __init__(self):
        self.hashes = {}
        self.stats = {}

    def digest(self, path):
        path = Path(path).resolve()
        if str(path) not in self.hashes:
            require(path.is_file(), f'Missing input: {path}')
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(block)
            self.hashes[str(path)] = digest.hexdigest()
            stat = path.stat()
            self.stats[str(path)] = (stat.st_size, stat.st_mtime_ns)
        return self.hashes[str(path)]

    def json(self, path):
        self.digest(path)
        return json.loads(Path(path).read_text(encoding='utf-8'))

    def unchanged(self):
        return all(Path(p).is_file() and (Path(p).stat().st_size, Path(p).stat().st_mtime_ns) == v
                   for p, v in self.stats.items())


def ownership_raster(polygons, bounds, cell=2.0):
    """Independent scan conversion; detect gaps, overlap and unclosed outlines."""
    x0, z0, x1, z1 = bounds
    nx, nz = int(round((x1 - x0) / cell)), int(round((z1 - z0) / cell))
    owner = np.full((nz, nx), -1, dtype=np.int16)
    coverage = np.zeros((nz, nx), dtype=np.uint8)
    for region_index, (region, polygon) in enumerate(polygons.items()):
        p = np.asarray(polygon, dtype=float)
        require(len(p) >= 3 and np.isfinite(p).all(), f'{region}: invalid ownership polygon')
        a, b = p, np.roll(p, -1, axis=0)
        for row in range(nz):
            z = z0 + (row + .5) * cell
            active = (a[:, 1] > z) != (b[:, 1] > z)
            lo, hi = a[active], b[active]
            crossings = np.sort(lo[:, 0] + (z - lo[:, 1]) * (hi[:, 0] - lo[:, 0]) / (hi[:, 1] - lo[:, 1]))
            require(len(crossings) % 2 == 0, f'{region}: odd scanline crossings at {z}')
            for left, right in crossings.reshape(-1, 2):
                start = max(0, int(np.ceil((left - x0) / cell - .5)))
                stop = min(nx, int(np.ceil((right - x0) / cell - .5)))
                coverage[row, start:stop] += 1
                owner[row, start:stop] = region_index
    require(np.all(coverage == 1), f'Ownership has {int((coverage == 0).sum())} missing and {int((coverage > 1).sum())} overlapping source cells')
    return owner


def parent_names(document):
    parents = {child: i for i, node in enumerate(document['nodes']) for child in node.get('children', [])}
    result = []
    for i in range(len(document['nodes'])):
        names, seen = [], set()
        while i is not None:
            require(i not in seen, 'Cyclic scene hierarchy')
            seen.add(i)
            names.append(document['nodes'][i].get('name', ''))
            i = parents.get(i)
        result.append(names)
    return result


def image_digest(document, body, index, path, inputs, client):
    image = document['images'][index]
    if 'uri' in image:
        require('://' not in image['uri'] and not image['uri'].startswith('data:'), f'{path}: nonlocal image URI')
        target = (path.parent / image['uri']).resolve()
        require(target.is_relative_to(client.resolve()), f'{path}: external image escapes client workspace')
        return inputs.digest(target)
    view = document['bufferViews'][image['bufferView']]
    start = view.get('byteOffset', 0)
    return hashlib.sha256(body[start:start + view['byteLength']]).hexdigest()


def material_signature(document, body, index, path, inputs, client):
    def texture(index):
        entry = document['textures'][index]
        return {'imageSha256': image_digest(document, body, entry['source'], path, inputs, client),
                'sampler': document.get('samplers', [])[entry['sampler']] if 'sampler' in entry else {}}
    def normalize(value):
        if isinstance(value, list):
            return [normalize(v) for v in value]
        if not isinstance(value, dict):
            return value
        result = {}
        for key, value in value.items():
            if key == 'name':
                continue
            if key.endswith('Texture') and isinstance(value, dict) and 'index' in value:
                result[key] = {**normalize({k:v for k,v in value.items() if k != 'index'}), 'texture': texture(value['index'])}
            else:
                result[key] = normalize(value)
        return result
    return json.dumps(normalize(document['materials'][index]), sort_keys=True, separators=(',', ':'))


class Surface:
    def __init__(self, bounds, polygons, inputs=None, client=CLIENT, cell=2.0):
        self.bounds = np.asarray(bounds, dtype=float)
        self.cell = cell
        self.ids = list(polygons)
        self.owner = ownership_raster(polygons, bounds, cell)
        self.nz, self.nx = np.array(self.owner.shape) + 1
        self.attributes = np.full((self.nx * self.nz, 12), np.nan)
        self.source_counts = np.zeros(self.owner.size * 2, dtype=np.uint32)
        self.inputs = inputs or Inputs()
        self.client = Path(client)
        self.material = None
        self.max_error = defaultdict(float)

    def vertex_indices(self, positions):
        horizontal = positions[:, [0, 2]]
        coordinates = (horizontal - self.bounds[:2]) / self.cell
        rounded = np.rint(coordinates).astype(np.int64)
        require(np.max(np.abs(coordinates - rounded), initial=0) < 0.0001, 'Terrain has vertices off the common two-metre lattice')
        require(np.all((rounded[:, 0] >= 0) & (rounded[:, 0] < self.nx) & (rounded[:, 1] >= 0) & (rounded[:, 1] < self.nz)), 'Terrain vertices outside continent bounds')
        return rounded[:, 1] * self.nx + rounded[:, 0]

    def face_indices(self, vertices, indices):
        triangles = vertices[indices.reshape(-1, 3)]
        x, z = triangles % self.nx, triangles // self.nx
        cx, cz = x.min(axis=1), z.min(axis=1)
        require(np.all((x.max(axis=1) - cx == 1) & (z.max(axis=1) - cz == 1)), 'Terrain contains non-source triangles or degenerate faces')
        code = np.sort((x - cx[:, None]) + (z - cz[:, None]) * 2, axis=1)
        first = np.all(code == [0, 1, 2], axis=1)
        second = np.all(code == [1, 2, 3], axis=1)
        require(np.all(first | second), 'Terrain uses a different diagonal than the shared source')
        winding = (x[:,1]-x[:,0])*(z[:,2]-z[:,0])-(z[:,1]-z[:,0])*(x[:,2]-x[:,0])
        require(np.all(winding < 0), 'Terrain face winding is reversed')
        return (cz * (self.nx - 1) + cx) * 2 + second.astype(int)

    def read(self, path, counts, region=None, source=False, bounds=None, manifest=None):
        path = Path(path).resolve()
        self.inputs.digest(path)
        doc, body = GR.load(path)
        matrices, _ = GR.hierarchy(doc)
        names = parent_names(doc)
        vertex_count = face_count = 0
        signatures = {}
        declared = manifest.get('externalResources', {}) if manifest else None
        actual_dependencies = {}
        for image_index, image in enumerate(doc.get('images', [])):
            if 'uri' in image:
                uri = image['uri']
                actual_dependencies[uri] = image_digest(doc, body, image_index, path, self.inputs, self.client)
        if declared is not None:
            require(actual_dependencies == declared, f'{path}: declared external resources differ from actual GLB image dependencies')
        primitive_cache = {}
        for index, node in enumerate(doc['nodes']):
            if 'mesh' not in node:
                continue
            matrix = matrices[index].copy()
            if region is not None:
                matrix[:3, 3] += self.translations[region]
            terrain_names = [n for n in names[index] if n.startswith('Terrain_')]
            territory = None
            if terrain_names:
                territory = next((r for r in self.ids if any(n.startswith('Terrain_' + r + '_') for n in terrain_names)), None)
                require(territory is not None, f'{path}: legacy or unidentified visible terrain {terrain_names[0]}')
                require(region is None or territory == region, f'{path}: contains another territory\'s terrain')
            if territory is None and bounds is None:
                continue
            for primitive in doc['meshes'][node['mesh']]['primitives']:
                position_index = primitive['attributes']['POSITION']
                if position_index not in primitive_cache:
                    primitive_cache[position_index] = GR.accessor(doc, body, position_index).astype(float)
                raw = primitive_cache[position_index]
                positions = raw @ matrix[:3, :3].T + matrix[:3, 3]
                if bounds is not None:
                    # Use actual vertices, not merely a placement origin or bbox centre.
                    local = positions - self.translations[region]
                    require(np.all(local >= np.asarray(bounds['min']) - .005) and np.all(local <= np.asarray(bounds['max']) + .005), f'{path}: rendered geometry extends outside declared loading bounds')
                if territory is None:
                    continue
                require(primitive.get('mode', 4) == 4 and 'indices' in primitive, f'{path}: terrain is not indexed triangles')
                attrs = primitive['attributes']
                require(all(k in attrs for k in ('NORMAL', 'TEXCOORD_0', 'COLOR_0')), f'{path}: terrain lost normals, UVs or biome colours')
                normals = GR.accessor(doc, body, attrs['NORMAL']).astype(float) @ np.linalg.inv(matrix[:3, :3])
                normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-12)
                uv = GR.accessor(doc, body, attrs['TEXCOORD_0'])
                color = GR.accessor(doc, body, attrs['COLOR_0'])
                require(color.shape[1] == 4, f'{path}: terrain colour schema changed')
                values = np.c_[positions, normals, uv, color]
                require(np.isfinite(values).all(), f'{path}: non-finite terrain attributes')
                vertices = self.vertex_indices(positions)
                if source:
                    present = np.isfinite(self.attributes[vertices, 0])
                    require(np.allclose(self.attributes[vertices[present]], values[present], atol=1e-5, rtol=0), f'{path}: source split has inconsistent shared attributes')
                    self.attributes[vertices] = values
                else:
                    difference = np.abs(self.attributes[vertices] - values)
                    for label, lo, hi, tolerance in (('position',0,3,.0001),('normal',3,6,.000002),('UV',6,8,.000002),('color',8,12,.000002)):
                        error = float(difference[:, lo:hi].max(initial=0))
                        self.max_error[label] = max(self.max_error[label], error)
                        require(np.isfinite(error) and error <= tolerance, f'{path}: shared {label} changed by {error}')
                faces = self.face_indices(vertices, GR.accessor(doc, body, primitive['indices']).ravel().astype(np.int64))
                owner = self.owner.ravel()[faces // 2]
                require(np.all(owner == self.ids.index(territory)), f'{path}: terrain faces cross named ownership')
                np.add.at(counts, faces, 1)
                material = primitive.get('material')
                require(material is not None, f'{path}: unmaterialed terrain')
                if material not in signatures:
                    signatures[material] = material_signature(doc, body, material, path, self.inputs, self.client)
                if self.material is None:
                    self.material = signatures[material]
                require(signatures[material] == self.material, f'{path}: terrain material or texture changes at partition')
                vertex_count += len(vertices)
                face_count += len(faces)
        return {'terrainTriangles':face_count, 'terrainVertices':vertex_count, 'externalDependencies':len(actual_dependencies)}

    def complete(self, counts, label):
        missing, duplicate = int((counts == 0).sum()), int((counts > 1).sum())
        require(not missing and not duplicate, f'{label}: {missing} missing and {duplicate} duplicated visible terrain triangles')


def audit_frames(publication, manifests, translations):
    checks = 0
    triggers = set()
    arrivals = []
    def position(region, tile):
        origin = manifests[region]['coordinateTransform']['serverOrigin']
        return np.array([tile[0] + .5 - origin[0] + translations[region][0],
                         origin[1] - tile[1] - .5 + translations[region][2]])
    for link in publication['connections']:
        if link['type'] != 'walk':
            continue
        a, b = link['ends']
        frames = [end['frame'] for end in (a,b)]
        global_anchors = [np.asarray(end['frame']['anchor']) + translations[end['region']] for end in (a,b)]
        require(np.allclose(global_anchors[0], global_anchors[1], atol=.00001, rtol=0), f'{link["id"]}: reciprocal global frame anchors differ')
        require(np.allclose(frames[0]['outward'], -np.asarray(frames[1]['outward']), atol=1e-9), f'{link["id"]}: reciprocal directions differ')
        for source, target in ((a,b),(b,a)):
            region = source['region']
            stored = [f for f in manifests[region]['streamingBorders'] if f['id'] == link['id']]
            require(len(stored) == 1 and stored[0]['anchor'] == source['frame']['anchor'] and stored[0]['outward'] == source['frame']['outward'], f'{link["id"]}: territory frame differs from publication')
            target_positions = {tuple(position(target['region'], lane['arrival'])):lane['arrival'] for lane in target['lanes']}
            require(len(source['lanes']) == 7 and len(target_positions) == 7, f'{link["id"]}: seven crossing lanes are not distinct')
            for lane in source['lanes']:
                point = tuple(position(region, lane['tile']))
                require(point in target_positions, f'{link["id"]}: crossing changes global actor coordinates')
                trigger = (region, *lane['tile'])
                require(trigger not in triggers, f'{link["id"]}: duplicate departure trigger')
                triggers.add(trigger)
                arrivals.append((target['region'], *target_positions[point]))
                checks += 1
    require(not set(arrivals) & triggers, 'A crossing arrival immediately triggers another crossing')
    return {'checkedLaneDirections':checks}


def audit_collision(surface, region, manifest, package, inputs, server=None):
    path = package / 'collision.bin'
    require(path.is_file(), f'{region}: missing EWCG collision')
    inputs.digest(path)
    raw = path.read_bytes()
    magic, version, _, width, height = struct.unpack_from('<4sHHII', raw)
    origin = manifest['coordinateTransform']['serverOrigin']
    cells = manifest['coordinateTransform']['serverCells']
    require(magic == b'EWCG' and version == 2 and [width,height] == [v*2 for v in cells], f'{region}: EWCG dimensions/format differ from its territory frame')
    require(len(raw) == 16 + width*height, f'{region}: EWCG byte length mismatch')
    collision = manifest['collision']
    require(collision.get('sourceGlbSha256') == inputs.digest(package/'world.glb'), f'{region}: collision is not derived from the current emitted geometry')
    encoding = collision['heightEncoding']
    grid = np.frombuffer(raw, dtype=np.uint8, offset=16).reshape(height,width)
    x0,z1 = -origin[0],origin[1]
    lx,lz = np.meshgrid(x0+(np.arange(width)+.5)*.5, z1-(np.arange(height)+.5)*.5)
    gx,gz = lx+surface.translations[region][0], lz+surface.translations[region][2]
    ground = triangle_sample(surface.attributes[:,1].reshape(surface.nz,surface.nx),gx,gz,*surface.bounds[:2],surface.cell)
    doc,body = GR.load(package/'world.glb')
    names = parent_names(doc)
    decks = [i for i,node in enumerate(doc['nodes']) if 'mesh' in node and any(n.startswith('Walk_') for n in names[i]) and not any(any(word in n.lower() for word in ('ceiling','soffit','underside','roof')) for n in names[i])]
    triangles = GR.triangles(doc,body,decks)
    covered, deck = GR.rasterise(triangles,width,height,x0,z1,.5,upward=1/np.sqrt(1+.65**2)-1e-9)
    expected = np.where(covered & (deck >= ground-.03), deck, ground)
    valid = grid > 0
    decoded = encoding['origin'] + grid.astype(float)*encoding['step']
    errors = np.abs(decoded[valid]-expected[valid])
    maximum = float(errors.max(initial=0))
    require(maximum <= encoding['step']*.501+.003, f'{region}: EWCG support height differs from actual emitted terrain/deck by {maximum:.4f}m')
    result = {'halfCells':int(valid.sum()),'maximumQuantizationErrorMetres':maximum,'encodingStepMetres':encoding['step']}
    if server is not None:
        server_path = server/'tools/collision'/f'{region}.escg.gz'
        inputs.digest(server_path)
        data = gzip.decompress(server_path.read_bytes())
        magic,version,stage,size = struct.unpack_from('<4sHHI',data)
        require(magic == b'ESCG' and version == 1 and cells == [size,size] and len(data) == 12+size*size, f'{region}: server collision frame differs from EWCG')
        served = np.frombuffer(data,dtype=np.uint8,offset=12).reshape(size,size)
        conservative = valid.reshape(size,2,size,2).all(axis=(1,3))
        require(not np.any((served>0)&~conservative), f'{region}: server opens tiles unsupported by the four authored half-cells')
        result.update(serverWalkableTiles=int((served>0).sum()),serverStageMillimetres=stage)
    return result


def composition_algorithm_sha(path):
    """Match the composition certificate without importing/running its builder."""
    source=Path(path).read_text(encoding='utf-8');lines=source.splitlines(keepends=True)
    functions={node.name:node for node in ast.parse(source).body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))}
    blocks=[]
    for name in ('prepare','ferry_landing'):
        require(name in functions,f'Composition builder omits {name}')
        node=functions[name]
        first=min([node.lineno,*[d.lineno for d in node.decorator_list]])
        blocks.append(''.join(inspect.getblock(lines[first-1:])))
    return hashlib.sha256(''.join(blocks).encode()).hexdigest()


def audit_shaping(client, continent, composition, inputs):
    plan_sha=inputs.digest(continent/'diagonal-plan.json')
    require(composition['planSha256']==plan_sha,'Composition uses a different landscape plan')
    shaping={name:[] for name in ('landscape.py','world_layout.py','content.py','assemblies.py','crown_support.py','westhaven_support.py','ferry_export.py','ferry_support.py','mirror_support.py','manymouth_support.py','mirror_streets.py','four_gates_support.py','amberwood_support.py','amberwood_access.py','mirror_lake_support.py','ssarathi_bank_support.py','manymouth_boats.py','terrain_export.py','scene_io.py','grey_crossings.py','four_gates_sage.py','door_approaches.py','hull_settle.py','resource_trails.py','object_edits.py')}
    for relative,expected in composition['sources'].items():
        path=Path(relative.replace('\\','/'))
        if path.name in shaping:shaping[path.name].append((path,expected))
    for name,records in shaping.items():
        require(len(records)==1,f'Composition must identify exactly one shaping source: {name}')
        relative,expected=records[0];path=(client/relative).resolve()
        require(path==(continent/name).resolve(),f'Composition shaping source resolves outside its authored location: {relative}')
        require(inputs.digest(path)==expected,f'Authored landscape changed after composition: {relative}')
    builder=continent/'build_continent.py';inputs.digest(builder)
    algorithm_sha=composition_algorithm_sha(builder)
    require(composition.get('compositionAlgorithmSha256')==algorithm_sha,'Composition algorithm changed after composition')
    entrance_sha=inputs.digest(continent/'legacy-server-profile/config/eloria/maps.txt')
    require(composition.get('entranceProfileSha256')==entrance_sha,'Authored entrance profile changed after composition')
    edits_path=continent/'continent-edits.json'
    edits_sha=inputs.digest(edits_path) if edits_path.exists() else hashlib.sha256(b'').hexdigest()
    require(composition.get('objectEditsSha256',hashlib.sha256(b'').hexdigest())==edits_sha,'Object edits (continent-edits.json) changed after composition')
    return {'planSha256':plan_sha,'objectEditsSha256':edits_sha,'compositionAlgorithmSha256':algorithm_sha,'entranceProfileSha256':entrance_sha,'shapingModules':list(shaping)}


def exported_frames(client, exports, plan, master_sha, plan_sha, inputs):
    """Read the new export's frames without consulting an older publication."""
    plan_regions={r['id']:r for r in plan['regions']}
    require(len(plan_regions)==len(plan['regions']) and set(exports['regions'])==set(plan_regions),
            'Exported named territory set differs from continent plan')
    frames={};manifests={};packages={}
    for region in plan_regions:
        path=Path(exports['regions'][region]['world'])
        if not path.is_absolute():path=client/path
        path=path.resolve()
        require(path.is_relative_to(client.resolve()) and path.name=='world.json',f'{region}: exported territory manifest escapes the client')
        manifest=inputs.json(path);geo=manifest['continentGeography'];frame=manifest['coordinateTransform']
        require(manifest['asset']['id']==region,f'{region}: export points to another named territory')
        require(geo.get('geometryMode')=='continent-chunks-v1',f'{region}: named manifest is not a shared-continent export')
        source=manifest['singleContinentSource']
        require(source['masterSha256']==master_sha,f'{region}: territory references a different master')
        require(source['planSha256']==plan_sha,f'{region}: territory references a different landscape plan')
        translation=np.asarray(geo['translation'],float);center=np.asarray(plan_regions[region]['center'],float)
        require(translation.shape==(3,) and np.isfinite(translation).all() and
                np.allclose(translation,[center[0],0,center[1]],atol=1e-6,rtol=0),f'{region}: translation differs from the authored territory centre')
        origin=np.asarray(frame['serverOrigin'],float);cells=np.asarray(frame['serverCells'],float)
        require(origin.shape==(2,) and cells.shape==(2,) and np.isfinite(origin).all() and
                np.isfinite(cells).all() and (cells>0).all() and np.equal(cells,np.rint(cells)).all(),
                f'{region}: invalid exported server address frame')
        require(frame.get('metresPerTile')==1 and frame.get('invertServerY') is True and
                frame.get('origin')==[0,0,0],f'{region}: unsupported exported server coordinate transform')
        address=frame['addressableWorldBounds']
        expected={'min':[-origin[0],origin[1]-cells[1]],'max':[cells[0]-origin[0],origin[1]]}
        require(all(np.array_equal(address[k],expected[k]) for k in ('min','max')),f'{region}: exported address bounds disagree with its origin/dimensions')
        polygon=np.asarray(geo['ownershipPolygon'],float)
        require(polygon.ndim==2 and polygon.shape[1]==2 and len(polygon)>=3 and np.isfinite(polygon).all(),
                f'{region}: invalid exported ownership polygon')
        local=polygon-translation[[0,2]]
        require(np.all(local>=np.asarray(address['min'])-.001) and np.all(local<=np.asarray(address['max'])+.001),
                f'{region}: ownership extends beyond its exported server address')
        frames[region]={'translation':geo['translation'],'ownershipPolygon':geo['ownershipPolygon'],
                        'serverOrigin':frame['serverOrigin'],'serverCells':frame['serverCells']}
        manifests[region]=manifest;packages[region]=path.parent
    return frames,manifests,packages


def run(client, generated, report_path, server=None, require_collision=False, geometry_only=False):
    started = time.monotonic()
    inputs = Inputs()
    report = {'schema':1,'passed':False,'complete':False,'publicationVerified':False,'scope':'geometry-only' if geometry_only else 'full-publication','errors':[],'regions':{},'limitations':[
        ('This provisional audit excludes collision, route publication, camera obstruction, residency timing and moving actors.' if geometry_only else
         'This audit checks emitted static geometry and collision; camera obstruction, residency timing and moving actors require the live client.'),
        'Terrain, normals, UVs and biome colours are checked exhaustively; retained object loading bounds/dependencies are checked without comparing every object triangle to the master.']}
    try:
        report['auditSha256']=inputs.digest(Path(__file__))
        require(not geometry_only or server is None and not require_collision, 'Geometry-only cannot also request server/collision validation')
        base = client/'eloria-assets/maps/nymara-regions'
        continent=base/'_continent'
        plan = inputs.json(continent/'diagonal-plan.json')
        composition = inputs.json(generated/'composition.json')
        master_record = inputs.json(generated/'master-scene.json')
        exports = inputs.json(generated/'export.json')
        require(exports.get('compositionSha256')==inputs.digest(generated/'composition.json'),'Geometry differs from the current composition')
        report['shapingFreshness']=audit_shaping(client,continent,composition,inputs)
        required_export_sources={'build_continent.py','scene_io.py','terrain_export.py','bridge_export.py','ferry_export.py','crossings.py','amberwood_access.py','manymouth_access.py','manymouth_village_streets.py','collision_export.py','mirror_access_geometry.py','grey_crossings.py'}
        require(set(exports.get('geometrySources',{}))==required_export_sources,'Geometry export must certify every export source')
        for name,expected in exports['geometrySources'].items():
            require(inputs.digest(continent/name)==expected,f'Geometry export source changed: {name}')
        report['geometrySourceFreshness']=exports['geometrySources']
        master_sha = inputs.digest(generated/'continent.glb')
        require(master_sha == master_record['sha256'] == exports['masterSha256'], 'Master scene provenance differs between exported artifacts')
        master_path=Path(exports['masterPath'])
        if not master_path.is_absolute():master_path=generated/master_path
        require(master_path.resolve()==(generated/'continent.glb').resolve(),'Export ledger references another master path')
        shared_sha=inputs.digest(generated/'shared-terrain.glb')
        frames,manifests,packages=exported_frames(client,exports,plan,master_sha,composition['planSha256'],inputs)
        require(set(master_record['regions'])==set(frames),'Master scene named territory set differs from its export')
        if not geometry_only:
            geography = inputs.json(base/'continent-geography.json')
            require(geography.get('geometryMode')=='continent-chunks-v1','The canonical continent-chunks-v1 publication is not ready')
            require(master_sha==geography['verification']['masterSha256'],'Master scene provenance differs from canonical geography')
            require(shared_sha==geography['verification']['sharedSurfaceSha256'],'Shared terrain source digest differs from canonical geography')
            require(set(geography['regions'])==set(frames),'Canonical named territory set differs from the export')
            require(geography['ownershipRasterMetres']==2,'Canonical ownership lattice differs from shared terrain')
            for region,frame in frames.items():
                for key in ('ownershipPolygon','translation','serverOrigin','serverCells'):
                    require(frame[key]==geography['regions'][region][key],f'{region}: published {key} differs from its exported named manifest')
        polygons = {r:v['ownershipPolygon'] for r,v in frames.items()}
        surface = Surface(plan['bounds'],polygons,inputs,client,2.)
        surface.translations = {r:np.asarray(v['translation'],float) for r,v in frames.items()}
        report['frameAuthority']='export ledger, named manifests and authored plan' if geometry_only else 'canonical publication matched to exported named manifests'
        report['publicationVerified']=False
        surface.read(generated/'shared-terrain.glb',surface.source_counts,source=True)
        surface.complete(surface.source_counts,'Shared source')
        require(np.isfinite(surface.attributes).all(), 'Shared source omits vertices from the global lattice')
        master_counts = np.zeros_like(surface.source_counts)
        surface.read(generated/'continent.glb',master_counts)
        surface.complete(master_counts,'Master')
        named_counts = np.zeros_like(surface.source_counts)
        chunk_counts = np.zeros_like(surface.source_counts)
        for region in surface.ids:
            package=packages[region];manifest=manifests[region]
            stats = surface.read(package/'world.glb',named_counts,region=region,manifest=manifest)
            chunks = manifest['streamingChunks']['chunks']
            require(len(chunks) == len({c['id'] for c in chunks}) == exports['regions'][region]['chunks'], f'{region}: chunk inventory is inconsistent')
            require(chunks, f'{region}: empty chunk inventory')
            for chunk in chunks:
                child_path = (package/chunk['manifest']).resolve()
                require(child_path.is_relative_to(package.resolve()), f'{region}: chunk manifest escapes territory')
                child = inputs.json(child_path)
                require('streamingChunks' not in child, f'{child_path}: recursive chunk stream')
                require(child['bounds'] == chunk['bounds'], f'{child_path}: parent/child loading bounds differ')
                require(child['coordinateTransform'] == manifest['coordinateTransform'], f'{child_path}: chunk moved into a different coordinate frame')
                require(child['continentGeography']==manifest['continentGeography'] and child['singleContinentSource']==manifest['singleContinentSource'],
                        f'{child_path}: chunk ownership/master provenance differs from its named territory')
                glb = child_path.parent/child['asset']['glb']
                require(glb.stat().st_size == chunk['glbBytes'], f'{glb}: byte estimate is stale')
                surface.read(glb,chunk_counts,region=region,bounds=chunk['bounds'],manifest=child)
            stats['chunks'] = len(chunks)
            if not geometry_only and (require_collision or server is not None or (package/'collision.bin').is_file()):
                stats['collision'] = audit_collision(surface,region,manifest,package,inputs,server)
            report['regions'][region] = stats
            print(f'{region}: actual terrain, {len(chunks)} chunks, dependencies and bounds verified',flush=True)
        surface.complete(named_counts,'Named territories')
        surface.complete(chunk_counts,'Streaming chunks')
        if not geometry_only:
            publication = inputs.json(generated/'publication.json')
            report['frames'] = audit_frames(publication,manifests,surface.translations)
        if server is not None:
            served = inputs.json(server/'config/eloria/client_content_manifest.json')
            require(served['continentGeography']['masterSha256'] == master_sha, 'Server publishes a different continent master')
            client_graph = inputs.json(client/'godot-client/data/maps/exterior_connections.json')
            server_graph = inputs.json(server/'config/eloria/exterior_connections.json')
            require(client_graph == server_graph, 'Client/server adjacent-territory graphs differ')
        report.update(complete=not geometry_only,passed=True,sourceTerrainTriangles=len(surface.source_counts),
                      sourceTerrainVertices=len(surface.attributes),maximumSharedAttributeErrors=dict(surface.max_error),
                      masterSha256=master_sha,sharedSurfaceSha256=shared_sha,publicationVerified=not geometry_only)
    except (AuditError,KeyError,ValueError,TypeError,SyntaxError,OSError,struct.error) as error:
        report['errors'].append(str(error))
    report['unchangedDuringAudit'] = inputs.unchanged()
    if not report['unchangedDuringAudit']:
        report['errors'].append('Audited inputs changed during verification')
        report['passed'] = False
    report['elapsedSeconds'] = round(time.monotonic()-started,3)
    report['inputs'] = inputs.hashes
    report_path.parent.mkdir(parents=True,exist_ok=True)
    report_path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client',type=Path,default=CLIENT)
    parser.add_argument('--generated',type=Path,default=HERE/'generated')
    parser.add_argument('--server',type=Path)
    parser.add_argument('--output','--report',dest='report',type=Path,required=True)
    parser.add_argument('--require-collision',action='store_true')
    parser.add_argument('--geometry-only',action='store_true',help='Provisional exhaustive geometry check; excludes collision and published route contracts')
    args = parser.parse_args()
    report = run(args.client.resolve(),args.generated.resolve(),args.report.resolve(),args.server.resolve() if args.server else None,args.require_collision,args.geometry_only)
    print(json.dumps({k:report[k] for k in ('passed','complete','elapsedSeconds','errors')},indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
