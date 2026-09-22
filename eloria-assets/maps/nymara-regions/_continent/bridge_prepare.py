"""Prepare bridge geometry while composition may still change roads or ground."""


def prepare_bridges(world,content):
    """Fit claimed river sites after final water regeneration."""
    from bridge_export import fit_claimed_sites

    river_fit=fit_claimed_sites(world,content=content)
    river_ids=tuple(river_fit.get('selectedSiteIds',()))
    return {'claimedRiverFit':{'count':len(river_ids),'siteIds':river_ids}}
