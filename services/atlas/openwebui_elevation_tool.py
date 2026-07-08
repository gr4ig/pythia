"""
title: Offline Elevation (Terrain Tiles)
author: Gr4Ig
description: Look up ground elevation at any coordinate, or an elevation profile between two points, using local terrain tiles (30-80 m resolution in North America, ~300 m worldwide). No internet required. Combine with the offline geocoding tool to answer "how high is <place>".
required_open_webui_version: 0.4.0
version: 1.0.0
license: MIT
"""

import io
import math

import requests
from pydantic import BaseModel, Field


def _tile_for(lat: float, lon: float, z: int):
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    lat_r = math.radians(lat)
    y = (1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n
    xi = max(0, min(n - 1, int(x)))
    yi = max(0, min(n - 1, int(y)))
    px = int((x - xi) * 256)
    py = int((y - yi) * 256)
    return xi, yi, min(px, 255), min(py, 255)


class Tools:
    class Valves(BaseModel):
        tiles_url: str = Field(
            default="http://127.0.0.1:8096/terrain",
            description="Base URL of the local terrarium terrain tile service",
        )

    def __init__(self):
        self.valves = self.Valves()
        self.citation = True
        self._cache = {}

    def _elevation(self, lat: float, lon: float):
        """Return (elevation_m, zoom) or an error string."""
        try:
            from PIL import Image
        except ImportError:
            return "Pillow (PIL) is not available in this environment."
        for z in (12, 9):
            xi, yi, px, py = _tile_for(lat, lon, z)
            key = (z, xi, yi)
            img = self._cache.get(key)
            if img is None:
                try:
                    r = requests.get(
                        f"{self.valves.tiles_url}/{z}/{xi}/{yi}.png", timeout=20
                    )
                except requests.RequestException as e:
                    return f"Terrain tile service unreachable: {e}"
                if r.status_code != 200:
                    continue
                img = Image.open(io.BytesIO(r.content)).convert("RGB")
                if len(self._cache) > 32:
                    self._cache.clear()
                self._cache[key] = img
            rgb = img.getpixel((px, py))
            ele = (rgb[0] * 256 + rgb[1] + rgb[2] / 256) - 32768
            return ele, z
        return "No terrain tile available for this location."

    def get_elevation(self, lat: float, lon: float) -> str:
        """
        Get the ground elevation at a coordinate (offline terrain data;
        ~30-80 m grid in North America, ~300 m elsewhere). Negative values
        over ocean are seafloor depth (bathymetry).
        :param lat: Latitude in decimal degrees
        :param lon: Longitude in decimal degrees (negative for western hemisphere)
        """
        res = self._elevation(lat, lon)
        if isinstance(res, str):
            return res
        ele, z = res
        grid = "~40-80 m grid" if z == 12 else "~300 m grid"
        return (
            f"Elevation at lat {lat}, lon {lon}: {ele:.0f} m "
            f"({ele * 3.28084:.0f} ft) [{grid}]"
        )

    def get_elevation_profile(
        self,
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float,
        samples: int = 15,
    ) -> str:
        """
        Sample ground elevation along the straight line between two coordinates
        (offline). Returns the elevation at evenly spaced points plus min/max
        and total ascent, useful for judging terrain between two places.
        :param start_lat: Latitude of the starting point
        :param start_lon: Longitude of the starting point
        :param end_lat: Latitude of the end point
        :param end_lon: Longitude of the end point
        :param samples: Number of sample points including endpoints (default 15, max 50)
        """
        n = max(2, min(int(samples or 15), 50))
        pts = []
        for i in range(n):
            f = i / (n - 1)
            lat = start_lat + (end_lat - start_lat) * f
            lon = start_lon + (end_lon - start_lon) * f
            res = self._elevation(lat, lon)
            if isinstance(res, str):
                return res
            pts.append((f, res[0]))
        eles = [e for _, e in pts]
        ascent = sum(max(0, b - a) for a, b in zip(eles, eles[1:]))
        km = 6371.0 * math.acos(
            min(1.0, math.sin(math.radians(start_lat)) * math.sin(math.radians(end_lat))
                + math.cos(math.radians(start_lat)) * math.cos(math.radians(end_lat))
                * math.cos(math.radians(end_lon - start_lon)))
        )
        out = [
            f"Elevation profile over {km:.1f} km straight line "
            f"({n} samples): min {min(eles):.0f} m, max {max(eles):.0f} m, "
            f"total ascent {ascent:.0f} m.",
        ]
        out += [f"  {f*100:3.0f}%: {e:.0f} m" for f, e in pts]
        return "\n".join(out)
