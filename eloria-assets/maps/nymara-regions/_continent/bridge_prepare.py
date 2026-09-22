"""Prepare bridge geometry while composition may still change roads or ground."""


def prepare_bridges(world,content,*,selected_coastal_road_ids=None):
    """Apply coastal road edits, then freeze river and coastal bridge records."""
    from sea_crossings import (COMPONENT501_ROAD,DEFAULT_SELECTED_COASTAL_ROADS,
                               _selected_coastal_roads,apply_coastal_road_edits,
                               prepare_coastal_claims)
    from bridge_export import fit_claimed_sites,loose_crossing_inventory
    from coastal_bridge_export import build_selected_inventory

    selected=_selected_coastal_roads(DEFAULT_SELECTED_COASTAL_ROADS if selected_coastal_road_ids is None
                                     else selected_coastal_road_ids)
    road_edits=(tuple(apply_coastal_road_edits(world)) if COMPONENT501_ROAD in selected else ())
    river_fit=fit_claimed_sites(world,content=content)
    inventory=loose_crossing_inventory(world)
    coastal_records=tuple(prepare_coastal_claims(world,content=content,inventory=inventory,
                                                 selected_road_ids=selected))
    coastal_inventory=build_selected_inventory(inventory,coastal_records)
    world.claimed_coastal_records=coastal_records
    world.claimed_coastal_inventory=coastal_inventory
    river_ids=tuple(river_fit.get('selectedSiteIds',()))
    return {'coastalRoadEdits':{'count':len(road_edits),'roadIds':tuple(edit.road_id for edit in road_edits)},
            'claimedRiverFit':{'count':len(river_ids),'siteIds':river_ids},
            'coastalClaims':{'count':len(coastal_records),
                             'claimIds':tuple(claim.claim_id for claim in coastal_records),
                             'selectedRoadIds':selected,
                             'mode':coastal_inventory['mode'],
                             'authorityWetCells':len(coastal_inventory['authorityLooseWetCellIndices']),
                             'preparedWetCells':sum(len(row['looseWetCells']) for row in coastal_inventory['prepared']),
                             'fallbackWetCells':len(coastal_inventory['fallbackLooseWetCellIndices'])}}
