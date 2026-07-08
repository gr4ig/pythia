---
name: Offline Maps & Geography
description: Use this skill whenever the user asks about places, addresses, coordinates, distances, travel routes or times, elevation, terrain, or anything geographic. It explains how to combine the offline geocoding, routing, elevation, and wiki tools to answer multi-step geography questions without internet access.
compatibility:
  - Tools: offline_geocoding_photon, offline_routing_valhalla, offline_elevation_terrain, offline_places_poi, offline_almanac, offline_wikipedia_kiwix
---

# Offline Maps & Geography Instructions

All geographic knowledge is served by four LOCAL tools (no internet). Everything works from coordinates in decimal degrees; longitude is NEGATIVE in the Americas.

## Which tool for what
- **Place name or address → coordinates**: `geocode` (worldwide). For ambiguous names ("Springfield", "Paris"), pass `near_lat`/`near_lon` to bias toward a region, or include the state/country in the query.
- **Coordinates → what is there**: `reverse_geocode` (worldwide).
- **Routes, travel time, directions**: `get_route` / `compare_travel_modes` — **North America only** (Canada, USA, Mexico, Central America, Caribbean). Takes coordinates, not names. For anywhere else, say routing is unavailable offline.
- **Height / elevation / terrain**: `get_elevation`, `get_elevation_profile` — worldwide. ~40–80 m grid in North America, ~300 m elsewhere. Negative values over water are seafloor depth, not an error.
- **What's near a location** (hospitals, gas, groceries, campgrounds, water, any named business): `find_places_nearby` — North America only. Geocode the place first if you have a name.
- **Sunrise, sunset, moon phase, next full/new moon**: `get_sun_times` / `get_moon_info` — worldwide, any date.
- **Facts about a place** (population, history, description): the wiki search tool, not the geo tools.

## Composition patterns (do these without asking)
- "How far / how long from A to B" → `geocode` A, `geocode` B, then `get_route` with both coordinate pairs.
- "How high is X" → `geocode` X, then `get_elevation`. Prefer a wiki lookup for famous summits' official heights; use `get_elevation` for arbitrary spots.
- "What's the terrain like between A and B" → geocode both, `get_elevation_profile`.
- "What's at these coordinates" → `reverse_geocode`, optionally followed by a wiki search on the result's name.
- Combine freely: e.g. route first, then elevation profile between the same points to warn about mountain driving.
- "Nearest hospital to X" / "campgrounds near X" -> `geocode` X, then `find_places_nearby` with its coordinates.
- "When does the sun set in X on Saturday" -> `geocode` X, then `get_sun_times` with the date.

## Presenting results
- Give distances in both km and miles; elevations in both m and ft (the tools already format this).
- Cite which offline source answered (OpenStreetMap geocoder, Valhalla router, terrain tiles, wiki).
- The human can browse the map themselves at http://localhost:8095 (search box, topo toggle) — mention it when a visual map would help.

