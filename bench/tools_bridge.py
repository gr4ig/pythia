"""Load the REAL Open WebUI tool implementations from their service dirs and
expose them as Ollama-style tool schemas + an executor.

The benchmark measures the exact code paths Open WebUI runs, not mocks.
"""
import importlib.util
import json
import time
from pathlib import Path

AI = Path.home() / ".local/ai-services"

_SOURCES = {
    "kiwix": AI / "kiwix/openwebui_tool.py",
    "photon": AI / "photon/openwebui_tool.py",
    "valhalla": AI / "valhalla/openwebui_tool.py",
    "elevation": AI / "atlas/openwebui_elevation_tool.py",
    "poi": AI / "poi/openwebui_tool.py",
    "almanac": AI / "almanac/openwebui_tool.py",
}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(f"owui_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Tools()


_instances = {k: _load(k, v) for k, v in _SOURCES.items()}

# (tool_name, instance_key, method, schema)
_REGISTRY = [
    ("search_offline_wikis", "kiwix", "search_offline_wikis", {
        "description": "Full-text search across the offline wiki library (Wikipedia, Stack Exchange, etc). Returns article titles and books. Use get_wiki_article to read one.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Search terms"}},
            "required": ["query"]},
    }),
    ("get_wiki_article", "kiwix", "get_wiki_article", {
        "description": "Fetch the full text of an article from the offline wiki library.",
        "parameters": {"type": "object", "properties": {
            "title": {"type": "string", "description": "Exact article title"},
            "book": {"type": "string", "description": "Book name from search results (optional)"}},
            "required": ["title"]},
    }),
    ("geocode", "photon", "geocode", {
        "description": "Find places worldwide by name or address; returns type, address, and coordinates.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Place name or address"},
            "limit": {"type": "integer", "description": "Max matches (default 5)"},
            "near_lat": {"type": "number", "description": "Optional latitude bias"},
            "near_lon": {"type": "number", "description": "Optional longitude bias"}},
            "required": ["query"]},
    }),
    ("reverse_geocode", "photon", "reverse_geocode", {
        "description": "Find what is at or near a coordinate: nearest named places and addresses.",
        "parameters": {"type": "object", "properties": {
            "lat": {"type": "number"}, "lon": {"type": "number"},
            "limit": {"type": "integer", "description": "Max places (default 3)"}},
            "required": ["lat", "lon"]},
    }),
    ("get_route", "valhalla", "get_route", {
        "description": "Compute a route between two coordinates (North America only). Returns distance, travel time, turn-by-turn directions. Modes: auto, pedestrian, bicycle.",
        "parameters": {"type": "object", "properties": {
            "start_lat": {"type": "number"}, "start_lon": {"type": "number"},
            "end_lat": {"type": "number"}, "end_lon": {"type": "number"},
            "mode": {"type": "string", "description": "auto (default), pedestrian, or bicycle"}},
            "required": ["start_lat", "start_lon", "end_lat", "end_lon"]},
    }),
    ("get_elevation", "elevation", "get_elevation", {
        "description": "Ground elevation at a coordinate from offline terrain data (worldwide; negative over ocean = seafloor depth).",
        "parameters": {"type": "object", "properties": {
            "lat": {"type": "number"}, "lon": {"type": "number"}},
            "required": ["lat", "lon"]},
    }),
    ("find_places_nearby", "poi", "find_places_nearby", {
        "description": "Find points of interest near a coordinate (North America): hospitals, pharmacies, gas stations, groceries, campgrounds, water, hotels, or any named place.",
        "parameters": {"type": "object", "properties": {
            "lat": {"type": "number"}, "lon": {"type": "number"},
            "what": {"type": "string", "description": "e.g. 'hospital', 'gas station', 'campground', or a name like 'Walmart'"},
            "radius_km": {"type": "number", "description": "Search radius km (default 10)"},
            "limit": {"type": "integer", "description": "Max results (default 12)"}},
            "required": ["lat", "lon", "what"]},
    }),
    ("get_sun_times", "almanac", "get_sun_times", {
        "description": "Sunrise, sunset, and day length for a coordinate and date (offline ephemeris).",
        "parameters": {"type": "object", "properties": {
            "lat": {"type": "number"}, "lon": {"type": "number"},
            "date": {"type": "string", "description": "YYYY-MM-DD (default today)"},
            "tz_offset_hours": {"type": "number", "description": "Local UTC offset, e.g. -5 for CDT"}},
            "required": ["lat", "lon"]},
    }),
    ("get_moon_info", "almanac", "get_moon_info", {
        "description": "Moon phase and illumination for a date, plus next full and new moons.",
        "parameters": {"type": "object", "properties": {
            "date": {"type": "string", "description": "YYYY-MM-DD (default today)"}},
            "required": []},
    }),
    ("get_elevation_profile", "elevation", "get_elevation_profile", {
        "description": "Elevation profile along the straight line between two coordinates: sampled elevations, min/max, total ascent.",
        "parameters": {"type": "object", "properties": {
            "start_lat": {"type": "number"}, "start_lon": {"type": "number"},
            "end_lat": {"type": "number"}, "end_lon": {"type": "number"},
            "samples": {"type": "integer", "description": "Sample count (default 15)"}},
            "required": ["start_lat", "start_lon", "end_lat", "end_lon"]},
    }),
]


def ollama_tools():
    """Tool list in Ollama /api/chat format."""
    return [
        {"type": "function",
         "function": {"name": name, **schema}}
        for name, _, _, schema in _REGISTRY
    ]


def execute(name, args):
    """Run a tool call against the real local services. Returns (result_str, seconds)."""
    for reg_name, inst_key, method, _ in _REGISTRY:
        if reg_name == name:
            fn = getattr(_instances[inst_key], method)
            t0 = time.time()
            try:
                out = fn(**(args or {}))
            except TypeError as e:
                out = f"Bad tool arguments: {e}"
            except Exception as e:
                out = f"Tool error: {e}"
            return str(out), time.time() - t0
    return f"Unknown tool: {name}", 0.0


if __name__ == "__main__":
    print(json.dumps([t["function"]["name"] for t in ollama_tools()]))
    out, dt = execute("geocode", {"query": "Eiffel Tower", "limit": 1})
    print(f"[{dt:.2f}s]", out.splitlines()[1] if len(out.splitlines()) > 1 else out)
