"""
fetch_boundaries.py
===================

Fetch administrative boundaries for Lahore's towns from OpenStreetMap via the
Overpass API, and write them to data/geojson/lahore_towns.geojson.

WHY THIS SCRIPT EXISTS
----------------------
The hackathon submission is stronger with REAL administrative boundaries rather
than hand-drawn approximations. This script pulls admin_level=8 (and admin_level=6
as a fallback) relations tagged as towns/tehsils within Lahore.

USAGE
-----
    python backend/scripts/fetch_boundaries.py

If the Overpass query succeeds, it writes real boundaries.
If it fails (network blocked, Overpass down, names not matched), it falls back
to the committed approximate boundaries so the rest of the system keeps working.

IMPORTANT
---------
OSM town naming is inconsistent. Lahore's 9 administrative towns may appear under
slightly different names or admin levels. After running this, VISUALLY VERIFY the
output on geojson.io before relying on it. If OSM does not return clean polygons
for all 9 towns, keep the approximate fallback for the towns that are missing and
document this clearly (see docs/DATA_SOURCES.md).
"""

import json
import os
import sys
import time

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

# Overpass's main endpoint rejects requests with the default python-requests
# User-Agent (HTTP 406). A descriptive, honest User-Agent fixes this.
HEADERS = {"User-Agent": "HoshiyarLahore/0.4 (hackathon; contact: team@example.com)"}

# The 5 official tehsils of Lahore (2023 census). OSM naming varies,
# so we provide several possible name spellings per tehsil.
TOWN_NAME_CANDIDATES = {
    "lahore_city": ["Lahore City Tehsil", "Lahore City", "Tehsil Lahore City",
                    "Lahore City tehsil"],
    "shalimar": ["Shalimar Tehsil", "Shalamar Tehsil", "Shalimar Town",
                 "Tehsil Shalimar"],
    "model_town": ["Model Town Tehsil", "Model Town", "Tehsil Model Town"],
    "lahore_cantonment": ["Lahore Cantonment Tehsil", "Lahore Cantonment",
                          "Lahore Cantt", "Cantonment Tehsil"],
    "raiwind": ["Raiwind Tehsil", "Raiwind", "Tehsil Raiwind", "Raiwand Tehsil"],
}

# Lahore bounding box (roughly) to constrain the Overpass search:
# south, west, north, east
LAHORE_BBOX = (31.30, 74.15, 31.75, 74.60)

# Resolve paths relative to the repo root (this file is in backend/scripts/)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
OUTPUT_PATH = os.path.join(REPO_ROOT, "data", "geojson", "lahore_towns.geojson")
FALLBACK_PATH = os.path.join(
    REPO_ROOT, "data", "geojson", "lahore_towns_fallback.geojson"
)
METADATA_PATH = os.path.join(
    REPO_ROOT, "data", "metadata", "town_metadata.json"
)


# ---------------------------------------------------------------------------
# Overpass query
# ---------------------------------------------------------------------------

def build_overpass_query(names):
    """Build an Overpass QL query searching for boundary relations by name
    within the Lahore bounding box."""
    s, w, n, e = LAHORE_BBOX
    name_filters = "".join(
        f'  relation["boundary"="administrative"]["name"~"{name}",i]({s},{w},{n},{e});\n'
        for name in names
    )
    query = f"""[out:json][timeout:60];
(
{name_filters});
out body;
>;
out skel qt;
"""
    return query


def query_overpass(query):
    """Try each Overpass endpoint until one works. Returns parsed JSON or None."""
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            print(f"  Querying {endpoint} ...")
            resp = requests.post(endpoint, data={"data": query},
                                 headers=HEADERS, timeout=90)
            if resp.status_code == 200:
                return resp.json()
            print(f"    HTTP {resp.status_code} from {endpoint}")
        except requests.RequestException as exc:
            print(f"    Request failed for {endpoint}: {exc}")
        time.sleep(2)
    return None


# ---------------------------------------------------------------------------
# Geometry assembly
# ---------------------------------------------------------------------------

def assemble_polygon(osm_json):
    """
    Convert an Overpass response for a single relation into a list of
    [lon, lat] rings. This is a simplified assembler that stitches the
    relation's 'outer' ways into rings. For hackathon purposes we take the
    largest closed ring.

    Returns a GeoJSON-style coordinates array for a Polygon, or None.
    """
    nodes = {}
    ways = {}
    relations = []

    for element in osm_json.get("elements", []):
        if element["type"] == "node":
            nodes[element["id"]] = (element["lon"], element["lat"])
        elif element["type"] == "way":
            ways[element["id"]] = element.get("nodes", [])
        elif element["type"] == "relation":
            relations.append(element)

    if not relations:
        return None

    # Use the first administrative relation found
    relation = relations[0]
    outer_way_ids = [
        m["ref"] for m in relation.get("members", [])
        if m["type"] == "way" and m.get("role") in ("outer", "")
    ]

    # Collect coordinate sequences from outer ways
    segments = []
    for wid in outer_way_ids:
        node_ids = ways.get(wid, [])
        coords = [nodes[nid] for nid in node_ids if nid in nodes]
        if len(coords) >= 2:
            segments.append(coords)

    if not segments:
        return None

    # Naive stitching: concatenate all segments, then close the ring.
    ring = []
    for seg in segments:
        ring.extend(seg)
    if ring[0] != ring[-1]:
        ring.append(ring[0])

    if len(ring) < 4:
        return None

    return [ring]  # Polygon = list of rings


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def load_metadata():
    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    print("=" * 70)
    print("HoshiyarLahore - Boundary Fetcher")
    print("=" * 70)

    metadata = load_metadata()
    town_meta = {t["id"]: t for t in metadata["towns"]}

    features = []
    fetched_ids = set()

    for town_id, names in TOWN_NAME_CANDIDATES.items():
        print(f"\nFetching boundary for: {town_id} ({names[0]})")
        query = build_overpass_query(names)
        result = query_overpass(query)

        if result is None:
            print(f"  No Overpass response for {town_id}; will use fallback.")
            continue

        coords = assemble_polygon(result)
        if coords is None:
            print(f"  Could not assemble polygon for {town_id}; will use fallback.")
            continue

        meta = town_meta.get(town_id, {})
        features.append({
            "type": "Feature",
            "properties": {
                "id": town_id,
                "name": meta.get("name", town_id),
                "name_ur": meta.get("name_ur", ""),
                "source": "openstreetmap",
            },
            "geometry": {"type": "Polygon", "coordinates": coords},
        })
        fetched_ids.add(town_id)
        print(f"  OK: assembled polygon for {town_id}")
        time.sleep(1)  # be polite to Overpass

    # Fill any missing towns from the fallback file
    missing = set(TOWN_NAME_CANDIDATES) - fetched_ids
    if missing:
        print(f"\n{len(missing)} town(s) missing from OSM: {sorted(missing)}")
        print("Filling missing towns from fallback GeoJSON.")
        if os.path.exists(FALLBACK_PATH):
            with open(FALLBACK_PATH, "r", encoding="utf-8") as f:
                fallback = json.load(f)
            for feat in fallback["features"]:
                if feat["properties"]["id"] in missing:
                    features.append(feat)
                    print(f"  Added fallback polygon for {feat['properties']['id']}")
        else:
            print("  WARNING: fallback file not found. Some towns will be absent.")

    if not features:
        print("\nERROR: No boundaries obtained at all. Using entire fallback file.")
        if os.path.exists(FALLBACK_PATH):
            with open(FALLBACK_PATH, "r", encoding="utf-8") as f:
                fallback = json.load(f)
            features = fallback["features"]
        else:
            print("No fallback available. Aborting.")
            sys.exit(1)

    geojson = {"type": "FeatureCollection", "features": features}

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

    print(f"\nWrote {len(features)} town boundaries to:")
    print(f"  {OUTPUT_PATH}")
    print("\nNEXT STEP: open the file on https://geojson.io to visually verify")
    print("the polygons look correct before relying on them.")


if __name__ == "__main__":
    main()
