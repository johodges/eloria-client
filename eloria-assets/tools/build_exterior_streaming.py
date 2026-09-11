"""Publish proximity links from the continent graph and authored border surveys.

Run after rebuilding a paired border. Ferries retain their deliberate journeys.
Only reciprocal, surveyed collars permit a continuous visual handoff; every land
connection can still preload its destination without changing server authority.
"""
import json
import argparse
import re
from pathlib import Path

CLIENT = Path(__file__).resolve().parents[2]
REGIONS = CLIENT / 'eloria-assets/maps/nymara-regions'


def build(server=None):
    graph = json.loads((REGIONS / 'region-connections.json').read_text(encoding='utf-8'))
    registry = json.loads((CLIENT / 'godot-client/data/maps/registry.json').read_text(encoding='utf-8'))
    registry = registry.get('maps', registry)
    actors = json.loads((CLIENT / 'godot-client/data/actors/models.json').read_text(encoding='utf-8'))
    objects = json.loads((CLIENT / 'godot-client/data/world/objects.json').read_text(encoding='utf-8'))
    npc_types = {}
    if server:
        for line in (server / 'config/eloria/npcs.txt').read_text(encoding='utf-8').splitlines():
            fields = [p.strip() for p in line.split('|')]
            actor_type = re.search(r'actor_type=(\d+)', line)
            if len(fields) > 2 and fields[0] == 'npc' and actor_type:
                npc_types.setdefault(fields[2], set()).add(actor_type[1])
    result = []
    for link in graph['connections']:
        if link['type'] not in ('walk', 'causeway'): continue
        ends = []
        for key in ('from', 'to'):
            region = link[key]
            path = Path(registry[region]['manifest'].replace('res://', str(CLIENT / 'godot-client') + '/')).resolve()
            manifest = json.loads(path.read_text(encoding='utf-8'))
            entries = manifest.get('portals', []) + manifest.get('interactives', [])
            portal = next(p for p in entries if p.get('id') == link[key + '_portal'])
            frame = next((s for s in manifest.get('streamingBorders', []) if s['portal'] == portal['id']), {})
            visuals = set()
            harvest = objects['harvestables']
            resources = manifest.get('harvestables', []) + manifest.get('runtimePopulation', {}).get('resources', [])
            for resource in resources:
                key = harvest['resources'].get(resource.get('resource', ''))
                if key in harvest['models']: visuals.add(harvest['models'][key]['scene'])
            for actor_type in npc_types.get(region, []):
                key = actors['actorTypes'].get(actor_type)
                if key in actors['models']: visuals.add(actors['models'][key]['scene'])
            ends.append(dict(map=region, portal=portal['id'], position=portal['position'], frame=frame,
                             coordinateTransform=manifest['coordinateTransform'], visualScenes=sorted(visuals)))
        joined = bool(ends[0]['frame'] and ends[1]['frame'] and
                      ends[0]['frame']['id'] == ends[1]['frame']['id'])
        result.append(dict(id=link['from'] + '--' + link['to'], ends=ends, seamless=joined))
    return dict(schema=1, preloadDistance=170, retainDistance=220, maximumNeighbours=2, connections=result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', type=Path)
    args = parser.parse_args()
    target = CLIENT / 'godot-client/data/maps/exterior_connections.json'
    data = build(args.server)
    target.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    if args.server:
        (args.server / 'config/eloria/exterior_connections.json').write_text(
            json.dumps(data, indent=2) + '\n', encoding='utf-8')
    print(f"{len(data['connections'])} land connections; {sum(c['seamless'] for c in data['connections'])} surveyed joins")
