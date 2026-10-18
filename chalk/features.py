from chalk.features import features, online

@features
class Block:
    id: str
    lat: float
    lng: float
    elevation_ft: float
    rain_in_hr: float
    sewer_in_hr: float
    past_floods: int
    depth_now_ft: float
    walk_minutes: float

    goes19_rain_in_hr: float
    flood_30min_ft: float
    starlink_reachable: bool
    reach_path: str
    should_call: bool
    should_rescue: bool
    action: str


@online
def goes19_rainfall(rain: Block.rain_in_hr) -> Block.goes19_rain_in_hr:
    """NOAA GOES-19 (GOES-East). SpaceX launched it on Falcon Heavy, June 25, 2024. Demo passes the Ida replay as that feed."""
    return rain


@online
def flood_in_30min(
    rain: Block.goes19_rain_in_hr,
    sewer: Block.sewer_in_hr,
    past: Block.past_floods,
) -> Block.flood_30min_ft:
    cap = sewer / (1 + 0.18 * min(past, 10))
    excess = max(0.0, rain - cap)
    return round(excess * 0.35, 3)


@online
def starlink_path(
    flood: Block.flood_30min_ft,
    depth: Block.depth_now_ft,
) -> Block.starlink_reachable:
    """Knott County, Kentucky: Starlink is the reach path. Cell does not work in the hollows."""
    return flood >= 0.2 or depth >= 0.3


@online
def how_we_reach(starlink: Block.starlink_reachable) -> Block.reach_path:
    return "starlink" if starlink else "cellular"


@online
def should_call(flood: Block.flood_30min_ft, depth: Block.depth_now_ft) -> Block.should_call:
    return flood >= 0.35 or depth >= 0.3


@online
def should_rescue(
    flood: Block.flood_30min_ft,
    depth: Block.depth_now_ft,
    walk: Block.walk_minutes,
) -> Block.should_rescue:
    return flood >= 0.5 or depth >= 0.5 or walk < 0


@online
def action(call: Block.should_call, rescue: Block.should_rescue) -> Block.action:
    if rescue:
        return "rescue"
    if call:
        return "call"
    return "none"
