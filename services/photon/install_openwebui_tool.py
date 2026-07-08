#!/usr/bin/env python3
"""Register the Photon geocoding tool in Open WebUI's database.

Inserts (or replaces) the 'offline_geocoding_photon' row in the tool table,
mirroring how offline_routing_valhalla was installed. Safe to re-run.
"""
import json
import sqlite3
import time
from pathlib import Path

DB = Path.home() / "Library/Application Support/open-webui/data/webui.db"
CONTENT = (Path(__file__).parent / "openwebui_tool.py").read_text()
TOOL_ID = "offline_geocoding_photon"

SPECS = [
    {
        "name": "geocode",
        "description": (
            "Find places worldwide by name or address using the offline "
            "OpenStreetMap geocoder. Returns matching places with type, "
            "address, and coordinates (usable with the offline routing tool)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Place name or address to search for, e.g. 'Eiffel Tower' or 'Springfield, Illinois'",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of matches to return (default 5, max 20)",
                },
                "near_lat": {
                    "type": "number",
                    "description": "Optional latitude to bias results toward a location",
                },
                "near_lon": {
                    "type": "number",
                    "description": "Optional longitude to bias results toward a location",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "reverse_geocode",
        "description": (
            "Find what is at or near a coordinate (offline reverse geocoding): "
            "the nearest named places, streets, or addresses."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "lat": {"type": "number", "description": "Latitude in decimal degrees"},
                "lon": {
                    "type": "number",
                    "description": "Longitude in decimal degrees (negative for western hemisphere)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of nearby places to return (default 3, max 10)",
                },
            },
            "required": ["lat", "lon"],
        },
    },
]

DESCRIPTION = (
    "Look up places anywhere in the world by name (geocoding) or find what is "
    "at a given coordinate (reverse geocoding) using the local Photon geocoder "
    "built from OpenStreetMap. No internet required."
)
META = {
    "description": DESCRIPTION,
    "manifest": {
        "title": "Offline Geocoding (Photon)",
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
    (
        TOOL_ID,
        user_id,
        "Offline Geocoding (Photon)",
        CONTENT,
        json.dumps(SPECS),
        json.dumps(META),
        None,
        now,
        now,
    ),
)
con.commit()
print(f"installed {TOOL_ID} for user {user_id}")
con.close()
