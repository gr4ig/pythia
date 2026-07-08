#!/usr/bin/env python3
"""Register the almanac tool in Open WebUI's database (same pattern as the others).
Note: skyfield must be installed in Open WebUI's python env (done 2026-07-08)."""
import json
import sqlite3
import time
from pathlib import Path

DB = Path.home() / "Library/Application Support/open-webui/data/webui.db"
CONTENT = (Path(__file__).parent / "openwebui_tool.py").read_text()
TOOL_ID = "offline_almanac"

SPECS = [
    {
        "name": "get_sun_times",
        "description": (
            "Sunrise, sunset, and day length for a coordinate and date, computed "
            "offline. Get coordinates from the geocoding tool if needed."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "lat": {"type": "number", "description": "Latitude in decimal degrees"},
                "lon": {"type": "number", "description": "Longitude in decimal degrees (negative in the Americas)"},
                "date": {"type": "string", "description": "Date as YYYY-MM-DD (default today)"},
                "tz_offset_hours": {"type": "number", "description": "Local UTC offset in hours, e.g. -5 for CDT (optional)"},
            },
            "required": ["lat", "lon"],
        },
    },
    {
        "name": "get_moon_info",
        "description": "Moon phase and illumination for a date, plus the next full and new moons (offline).",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date as YYYY-MM-DD (default today)"},
            },
            "required": [],
        },
    },
]

DESCRIPTION = (
    "Sunrise, sunset, twilight, moon phase, and upcoming full/new moons for any "
    "place and date, computed offline from a local JPL ephemeris."
)
META = {
    "description": DESCRIPTION,
    "manifest": {
        "title": "Offline Almanac (Sun & Moon)",
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
    (TOOL_ID, user_id, "Offline Almanac (Sun & Moon)", CONTENT,
     json.dumps(SPECS), json.dumps(META), None, now, now),
)
con.commit()
print(f"installed {TOOL_ID} for user {user_id}")
con.close()
