"""
title: Offline Routing (Valhalla)
author: Gr4Ig
description: Compute driving, walking, and cycling routes anywhere in North America using the local Valhalla routing engine. Returns distance, travel time, and turn-by-turn directions. No internet required.
required_open_webui_version: 0.4.0
version: 1.0.0
license: MIT
"""

import json

import requests
from pydantic import BaseModel, Field

_MODES = {
    "auto": "driving",
    "pedestrian": "walking",
    "bicycle": "cycling",
}


def _fmt_duration(seconds: float) -> str:
    m = int(round(seconds / 60))
    if m < 60:
        return f"{m} min"
    return f"{m // 60} h {m % 60} min"


class Tools:
    class Valves(BaseModel):
        valhalla_url: str = Field(
            default="http://127.0.0.1:8002",
            description="Base URL of the local Valhalla routing service",
        )
        max_maneuvers: int = Field(
            default=40,
            description="Maximum number of turn-by-turn maneuvers returned",
        )

    def __init__(self):
        self.valves = self.Valves()
        self.citation = True

    def get_route(
        self,
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float,
        mode: str = "auto",
    ) -> str:
        """
        Compute a route between two coordinates using the offline Valhalla engine
        (North America coverage: Canada, USA, Mexico, Central America, Caribbean).
        Returns total distance, estimated travel time, and turn-by-turn directions.
        :param start_lat: Latitude of the starting point (decimal degrees)
        :param start_lon: Longitude of the starting point (decimal degrees, negative for western hemisphere)
        :param end_lat: Latitude of the destination
        :param end_lon: Longitude of the destination
        :param mode: Travel mode: "auto" (driving), "pedestrian" (walking), or "bicycle" (cycling)
        """
        mode = (mode or "auto").strip().lower()
        if mode not in _MODES:
            return (
                f"Unknown mode '{mode}'. Use one of: "
                + ", ".join(f"{k} ({v})" for k, v in _MODES.items())
            )
        try:
            resp = requests.post(
                f"{self.valves.valhalla_url}/route",
                json={
                    "locations": [
                        {"lat": start_lat, "lon": start_lon},
                        {"lat": end_lat, "lon": end_lon},
                    ],
                    "costing": mode,
                    "units": "kilometers",
                },
                timeout=60,
            )
        except requests.RequestException as e:
            return f"Routing service unreachable at {self.valves.valhalla_url}: {e}"
        if resp.status_code != 200:
            try:
                err = resp.json().get("error", resp.text[:300])
            except Exception:
                err = resp.text[:300]
            return (
                f"Routing failed ({resp.status_code}): {err}. "
                "Note: coverage is North America only, and both points must be "
                "near a mapped road or path."
            )
        trip = resp.json()["trip"]
        s = trip["summary"]
        km = s["length"]
        out = [
            f"{_MODES[mode].capitalize()} route: {km:.1f} km "
            f"({km * 0.621371:.1f} mi), about {_fmt_duration(s['time'])}.",
            "",
            "Turn-by-turn:",
        ]
        n = 0
        for leg in trip["legs"]:
            for m in leg["maneuvers"]:
                n += 1
                if n > self.valves.max_maneuvers:
                    out.append(
                        f"... ({sum(len(l['maneuvers']) for l in trip['legs']) - self.valves.max_maneuvers} more maneuvers omitted)"
                    )
                    break
                d = m.get("length", 0)
                dist = f" — {d:.1f} km" if d >= 0.1 else ""
                out.append(f"{n}. {m['instruction']}{dist}")
            if n > self.valves.max_maneuvers:
                break
        return "\n".join(out)

    def compare_travel_modes(
        self,
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float,
    ) -> str:
        """
        Compare driving, walking, and cycling for a trip between two coordinates:
        distance and estimated time for each mode (offline, North America only).
        :param start_lat: Latitude of the starting point (decimal degrees)
        :param start_lon: Longitude of the starting point (decimal degrees, negative for western hemisphere)
        :param end_lat: Latitude of the destination
        :param end_lon: Longitude of the destination
        """
        lines = []
        for mode, label in _MODES.items():
            try:
                resp = requests.post(
                    f"{self.valves.valhalla_url}/route",
                    json={
                        "locations": [
                            {"lat": start_lat, "lon": start_lon},
                            {"lat": end_lat, "lon": end_lon},
                        ],
                        "costing": mode,
                        "units": "kilometers",
                    },
                    timeout=60,
                )
                if resp.status_code != 200:
                    lines.append(f"- {label}: no route found")
                    continue
                s = resp.json()["trip"]["summary"]
                lines.append(
                    f"- {label}: {s['length']:.1f} km, {_fmt_duration(s['time'])}"
                )
            except requests.RequestException as e:
                return f"Routing service unreachable at {self.valves.valhalla_url}: {e}"
        return "Travel options:\n" + "\n".join(lines)
