#!/usr/bin/env python3
"""Register the POI tool in Open WebUI's database (same pattern as the others)."""
import json
import sqlite3
import time
from pathlib import Path

DB = Path.home() / "Library/Application Support/open-webui/data/webui.db"
CONTENT = (Path(__file__).parent / "openwebui_tool.py").read_text()
TOOL_ID = "offline_places_poi"

SPECS = [
    {
        "name": "find_places_nearby",
        "description": (
            "Find points of interest near a coordinate from the offline "
            "OpenStreetMap database (North America): hospitals, pharmacies, gas "
            "stations, groceries, campgrounds, drinking water, hotels, "
            "restaurants, or any named place. Geocode a place name first if you "
            "only have a name."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "lat": {"type": "number", "description": "Latitude of the search center"},
                "lon": {"type": "number", "description": "Longitude (negative in the Americas)"},
                "what": {"type": "string", "description": "What to find, e.g. 'hospital', 'gas station', 'campground', 'grocery', or a name like 'Walmart'"},
                "radius_km": {"type": "number", "description": "Search radius in km (default 10, max 100)"},
                "limit": {"type": "integer", "description": "Max results (default 12, max 30)"},
            },
            "required": ["lat", "lon", "what"],
        },
    },
]

DESCRIPTION = (
    "Find points of interest near a coordinate — hospitals, pharmacies, gas "
    "stations, groceries, campgrounds, water sources, and any named place — "
    "from the offline OpenStreetMap database (North America)."
)
META = {
    "description": DESCRIPTION,
    "manifest": {
        "title": "Offline Places Nearby (OSM POI)",
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
    (TOOL_ID, user_id, "Offline Places Nearby (OSM POI)", CONTENT,
     json.dumps(SPECS), json.dumps(META), None, now, now),
)
con.commit()
print(f"installed {TOOL_ID} for user {user_id}")
con.close()
