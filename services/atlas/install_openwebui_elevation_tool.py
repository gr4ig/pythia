#!/usr/bin/env python3
"""Register the elevation tool in Open WebUI's database (same pattern as photon/valhalla)."""
import json
import sqlite3
import time
from pathlib import Path

DB = Path.home() / "Library/Application Support/open-webui/data/webui.db"
CONTENT = (Path(__file__).parent / "openwebui_elevation_tool.py").read_text()
TOOL_ID = "offline_elevation_terrain"

SPECS = [
    {
        "name": "get_elevation",
        "description": (
            "Get the ground elevation at a coordinate from offline terrain data "
            "(~40-80 m grid in North America, ~300 m elsewhere). Negative values "
            "over ocean are seafloor depth."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "lat": {"type": "number", "description": "Latitude in decimal degrees"},
                "lon": {
                    "type": "number",
                    "description": "Longitude in decimal degrees (negative for western hemisphere)",
                },
            },
            "required": ["lat", "lon"],
        },
    },
    {
        "name": "get_elevation_profile",
        "description": (
            "Sample ground elevation along the straight line between two "
            "coordinates (offline). Returns elevations at evenly spaced points, "
            "min/max, and total ascent."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "start_lat": {"type": "number", "description": "Latitude of the starting point"},
                "start_lon": {"type": "number", "description": "Longitude of the starting point"},
                "end_lat": {"type": "number", "description": "Latitude of the end point"},
                "end_lon": {"type": "number", "description": "Longitude of the end point"},
                "samples": {
                    "type": "integer",
                    "description": "Number of sample points including endpoints (default 15, max 50)",
                },
            },
            "required": ["start_lat", "start_lon", "end_lat", "end_lon"],
        },
    },
]

DESCRIPTION = (
    "Look up ground elevation at any coordinate, or an elevation profile "
    "between two points, using local terrain tiles. No internet required."
)
META = {
    "description": DESCRIPTION,
    "manifest": {
        "title": "Offline Elevation (Terrain Tiles)",
        "author": "Gr4Ig",
        "description": DESCRIPTION,
        "required_open_webui_version": "0.4.0",
        "version": "1.0.0",
        "license": "MIT",
    },
}

con = sqlite3.connect(DB)
user_id = con.execute(
    "SELECT user_id FROM tool WHERE id='offline_routing_valhalla'"
).fetchone()[0]
now = int(time.time())
con.execute(
    "INSERT OR REPLACE INTO tool (id, user_id, name, content, specs, meta, valves, updated_at, created_at) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
    (TOOL_ID, user_id, "Offline Elevation (Terrain Tiles)", CONTENT,
     json.dumps(SPECS), json.dumps(META), None, now, now),
)
con.commit()
print(f"installed {TOOL_ID} for user {user_id}")
con.close()
