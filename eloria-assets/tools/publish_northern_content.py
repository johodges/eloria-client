"""Record the northern regions' actual served NPCs, resources and encounters."""
import argparse
import json
from pathlib import Path
import sys

CLIENT = Path(__file__).resolve().parents[2]
REGIONS = CLIENT/'eloria-assets/maps/nymara-regions'
EXTERIORS = ('amberwood', 'whitehorn_range', 'grey_moors', 'mirrorhold', 'amethyst_barrens')


def publish(server):
    sys.path[:0] = [str(server), str(REGIONS/'_toolkit')]
    from eloria.npcs import load_npcs
    from eloria.harvesting import load_harvesting
    from eloria.spawns import load_spawns
    from contentposts import apply_runtime
    profile = server/'config/eloria'
    npcs = load_npcs(profile/'npcs.txt')
    _, resources = load_harvesting(profile/'harvesting.txt')
    spawns = load_spawns(profile/'spawns.txt')
    for region in EXTERIORS:
        package = REGIONS/region
        path = package/'world.json'
        manifest = json.loads(path.read_text(encoding='utf-8'))
        def tile(entry):
            return {'serverTile': [entry.x, entry.y], 'authority': 'server'}
        roster = {
            'npcs': [dict(id=n.name, name=n.name, role=n.role, **tile(n)) for n in sorted(npcs,key=lambda n:n.name) if n.map_id == region],
            'resources': [dict(id=identity, resource=n.resource, **tile(n))
                          for (map_id, identity), n in sorted(resources.items()) if map_id == region],
            'encounters': [dict(creature=n.creature, **tile(n)) for n in spawns if n.map_id == region],
        }
        (package/'source/runtime-content.json').write_text(json.dumps(roster, indent=2)+'\n', encoding='utf-8')
        apply_runtime(manifest, package)
        path.write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
        print(region, {k: len(v) for k, v in roster.items()})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', required=True, type=Path)
    args = parser.parse_args()
    publish(args.server.resolve())
