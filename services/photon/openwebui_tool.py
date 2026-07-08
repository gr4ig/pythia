"""
title: Offline Geocoding (Photon)
author: Gr4Ig
description: Look up places anywhere in the world by name (geocoding) or find what is at a given coordinate (reverse geocoding) using the local Photon geocoder built from OpenStreetMap. Returns names, addresses, and coordinates. No internet required. Combine with the offline routing tool: geocode two places, then route between their coordinates.
required_open_webui_version: 0.4.0
version: 1.0.0
license: MIT
"""

import requests
from pydantic import BaseModel, Field


def _fmt_feature(f: dict) -> str:
    p = f.get("properties", {})
    lon, lat = f["geometry"]["coordinates"][:2]
    name = p.get("name") or ", ".join(
        x for x in (p.get("street"), p.get("housenumber")) if x
    ) or "(unnamed)"
    kind = p.get("osm_value") or p.get("type") or ""
    addr_parts = [
        p.get(k)
        for k in ("street", "district", "city", "county", "state", "country")
        if p.get(k) and p.get(k) != name
    ]
    # de-duplicate while keeping order
    seen = set()
    addr = ", ".join(a for a in addr_parts if not (a in seen or seen.add(a)))
    line = f"{name}"
    if kind:
        line += f" [{kind}]"
    if addr:
        line += f" — {addr}"
    line += f" — lat {lat:.5f}, lon {lon:.5f}"
    return line


class Tools:
    class Valves(BaseModel):
        photon_url: str = Field(
            default="http://127.0.0.1:2322",
            description="Base URL of the local Photon geocoding service",
        )

    def __init__(self):
        self.valves = self.Valves()
        self.citation = True

    def geocode(
        self,
        query: str,
        limit: int = 5,
        near_lat: float = None,
        near_lon: float = None,
    ) -> str:
        """
        Find places worldwide by name or address (offline OpenStreetMap
        geocoder). Returns matching places with their type, address, and
        coordinates. Use the coordinates with the offline routing tool to
        compute routes between named places.
        :param query: Place name or address to search for, e.g. "Eiffel Tower", "1600 Pennsylvania Avenue, Washington", "Springfield, Illinois"
        :param limit: Maximum number of matches to return (default 5, max 20)
        :param near_lat: Optional latitude to bias results toward a location
        :param near_lon: Optional longitude to bias results toward a location
        """
        params = {
            "q": query,
            "limit": max(1, min(int(limit or 5), 20)),
            "lang": "en",
        }
        if near_lat is not None and near_lon is not None:
            params["lat"] = near_lat
            params["lon"] = near_lon
        try:
            resp = requests.get(
                f"{self.valves.photon_url}/api", params=params, timeout=30
            )
        except requests.RequestException as e:
            return f"Geocoding service unreachable at {self.valves.photon_url}: {e}"
        if resp.status_code != 200:
            return f"Geocoding failed ({resp.status_code}): {resp.text[:300]}"
        features = resp.json().get("features", [])
        if not features:
            return f"No places found matching '{query}'."
        out = [f"Places matching '{query}':"]
        for i, f in enumerate(features, 1):
            out.append(f"{i}. {_fmt_feature(f)}")
        return "\n".join(out)

    def reverse_geocode(self, lat: float, lon: float, limit: int = 3) -> str:
        """
        Find what is at or near a coordinate (offline reverse geocoding):
        the nearest named places, streets, or addresses.
        :param lat: Latitude in decimal degrees
        :param lon: Longitude in decimal degrees (negative for western hemisphere)
        :param limit: Maximum number of nearby places to return (default 3, max 10)
        """
        try:
            resp = requests.get(
                f"{self.valves.photon_url}/reverse",
                params={
                    "lat": lat,
                    "lon": lon,
                    "limit": max(1, min(int(limit or 3), 10)),
                    "lang": "en",
                },
                timeout=30,
            )
        except requests.RequestException as e:
            return f"Geocoding service unreachable at {self.valves.photon_url}: {e}"
        if resp.status_code != 200:
            return f"Reverse geocoding failed ({resp.status_code}): {resp.text[:300]}"
        features = resp.json().get("features", [])
        if not features:
            return f"Nothing found near lat {lat}, lon {lon}."
        out = [f"At or near lat {lat}, lon {lon}:"]
        for i, f in enumerate(features, 1):
            out.append(f"{i}. {_fmt_feature(f)}")
        return "\n".join(out)
