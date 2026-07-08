"""
title: Offline Places Nearby (OSM POI)
author: Gr4Ig
description: Find points of interest near a coordinate — hospitals, pharmacies, gas stations, groceries, campgrounds, water sources, and any other named place — from the offline OpenStreetMap database (North America). Combine with the offline geocoding tool: geocode a place name first, then search near its coordinates.
required_open_webui_version: 0.4.0
version: 1.0.0
license: MIT
"""

import json
import math
import sqlite3

from pydantic import BaseModel, Field

# common words -> OSM (key, value) pairs
_SYNONYMS = {
    "hospital": [("amenity", "hospital"), ("healthcare", "hospital")],
    "emergency room": [("amenity", "hospital")],
    "urgent care": [("amenity", "clinic"), ("healthcare", "clinic")],
    "clinic": [("amenity", "clinic"), ("healthcare", "clinic")],
    "doctor": [("amenity", "doctors"), ("healthcare", "doctor")],
    "pharmacy": [("amenity", "pharmacy"), ("shop", "chemist")],
    "drugstore": [("amenity", "pharmacy"), ("shop", "chemist")],
    "gas": [("amenity", "fuel")],
    "gas station": [("amenity", "fuel")],
    "fuel": [("amenity", "fuel")],
    "charging station": [("amenity", "charging_station")],
    "ev charger": [("amenity", "charging_station")],
    "grocery": [("shop", "supermarket"), ("shop", "convenience"), ("shop", "greengrocer")],
    "supermarket": [("shop", "supermarket")],
    "food": [("amenity", "restaurant"), ("amenity", "fast_food"), ("shop", "supermarket")],
    "restaurant": [("amenity", "restaurant")],
    "coffee": [("amenity", "cafe")],
    "cafe": [("amenity", "cafe")],
    "hotel": [("tourism", "hotel"), ("tourism", "motel")],
    "motel": [("tourism", "motel"), ("tourism", "hotel")],
    "campground": [("tourism", "camp_site")],
    "campsite": [("tourism", "camp_site")],
    "camping": [("tourism", "camp_site")],
    "water": [("amenity", "drinking_water"), ("amenity", "water_point")],
    "drinking water": [("amenity", "drinking_water"), ("amenity", "water_point")],
    "shelter": [("amenity", "shelter")],
    "toilet": [("amenity", "toilets")],
    "restroom": [("amenity", "toilets")],
    "police": [("amenity", "police")],
    "fire station": [("amenity", "fire_station")],
    "hardware": [("shop", "hardware"), ("shop", "doityourself")],
    "laundry": [("shop", "laundry")],
    "bank": [("amenity", "bank")],
    "atm": [("amenity", "atm")],
    "library": [("amenity", "library")],
    "school": [("amenity", "school")],
    "church": [("amenity", "place_of_worship")],
    "worship": [("amenity", "place_of_worship")],
    "dentist": [("amenity", "dentist"), ("healthcare", "dentist")],
    "vet": [("amenity", "veterinary")],
    "veterinarian": [("amenity", "veterinary")],
    "airport": [("aeroway", "aerodrome")],
    "bar": [("amenity", "bar"), ("amenity", "pub")],
    "mechanic": [("shop", "car_repair")],
    "car repair": [("shop", "car_repair")],
    "defibrillator": [("emergency", "defibrillator")],
    "hut": [("tourism", "wilderness_hut"), ("tourism", "alpine_hut")],
}


def _haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class Tools:
    class Valves(BaseModel):
        db_path: str = Field(
            default="~/.local/ai-services/poi/pois.sqlite",
            description="Path to the offline POI SQLite database (internal disk: Open WebUI opens this file directly, and the app may lack the removable-volume TCC grant; a backup copy lives on the SSD)",
        )

    def __init__(self):
        self.valves = self.Valves()
        self.citation = True

    def find_places_nearby(
        self,
        lat: float,
        lon: float,
        what: str,
        radius_km: float = 10,
        limit: int = 12,
    ) -> str:
        """
        Find points of interest near a coordinate from the offline OpenStreetMap
        database (North America coverage): hospitals, pharmacies, gas stations,
        grocery stores, campgrounds, drinking water, hotels, restaurants, or any
        named place. Get coordinates from the geocoding tool first if you only
        have a place name.
        :param lat: Latitude of the search center (decimal degrees)
        :param lon: Longitude of the search center (negative in the Americas)
        :param what: What to look for, e.g. "hospital", "gas station", "campground", "grocery", or a place name like "Walmart"
        :param radius_km: Search radius in kilometers (default 10, max 100)
        :param limit: Maximum results (default 12, max 30)
        """
        radius_km = max(0.5, min(float(radius_km or 10), 100))
        limit = max(1, min(int(limit or 12), 30))
        w = (what or "").strip().lower()
        try:
            con = sqlite3.connect(f"file:{self.valves.db_path}?mode=ro", uri=True)
        except sqlite3.Error as e:
            return f"POI database unavailable at {self.valves.db_path}: {e}"

        dlat = radius_km / 111.0
        dlon = radius_km / max(0.1, 111.0 * math.cos(math.radians(lat)))
        box = (lat - dlat, lat + dlat, lon - dlon, lon + dlon)

        pairs = _SYNONYMS.get(w, [])
        pair_conds, params = [], []
        for k, v in pairs:
            pair_conds.append("(p.key=? AND p.value=?)")
            params += [k, v]
        pair_sql = " OR ".join(pair_conds) if pair_conds else "0"
        # rank 0: exact category match; 1: raw category value; 2: name match only
        params_rank = list(params)
        params_where = list(params)
        val_like = f"%{w.replace(' ', '_')}%"
        name_like = f"%{w}%"

        sql = f"""
            SELECT p.name, p.key, p.value, p.lat, p.lon, p.extra,
                   CASE WHEN ({pair_sql}) THEN 0
                        WHEN p.value LIKE ? THEN 1
                        ELSE 2 END AS rank
            FROM poi_rtree r JOIN poi p ON p.id = r.id
            WHERE r.min_lat >= ? AND r.max_lat <= ?
              AND r.min_lon >= ? AND r.max_lon <= ?
              AND (({pair_sql}) OR p.value LIKE ? OR p.name LIKE ?)
        """
        try:
            rows = con.execute(
                sql,
                params_rank + [val_like] + list(box)
                + params_where + [val_like, name_like],
            ).fetchall()
        except sqlite3.Error as e:
            return f"POI query failed: {e}"
        finally:
            con.close()

        scored = []
        for name, key, value, plat, plon, extra, rank in rows:
            d = _haversine_km(lat, lon, plat, plon)
            if d <= radius_km:
                scored.append((d, name, value, plat, plon, extra, rank))
        # category matches first, then nearest
        scored.sort(key=lambda x: (x[6], x[0]))
        if not scored:
            return (
                f"No '{what}' found within {radius_km:g} km of lat {lat}, lon {lon} "
                "(offline OSM data, North America only). Try a larger radius or a "
                "different term."
            )
        out = [f"'{what}' within {radius_km:g} km of lat {lat}, lon {lon} "
               f"({min(len(scored), limit)} of {len(scored)} shown, nearest first):"]
        for d, name, value, plat, plon, extra, _rank in scored[:limit]:
            bits = [f"{d:.1f} km"]
            if extra:
                x = json.loads(extra)
                addr = " ".join(filter(None, [x.get("addr:housenumber"), x.get("addr:street")]))
                city = x.get("addr:city")
                if addr:
                    bits.append(addr + (f", {city}" if city else ""))
                elif city:
                    bits.append(city)
                if x.get("opening_hours"):
                    bits.append(f"hours: {x['opening_hours']}")
            out.append(
                f"- {name or '(unnamed)'} [{value.replace('_', ' ')}] — "
                + "; ".join(bits)
                + f" — lat {plat}, lon {plon}"
            )
        return "\n".join(out)
