"""
title: Offline Almanac (Sun & Moon)
author: Gr4Ig
description: Sunrise, sunset, twilight, moon phase, and upcoming full/new moons for any place and date, computed offline from a local JPL ephemeris. Combine with the offline geocoding tool: geocode a place name, then use its coordinates here.
required_open_webui_version: 0.4.0
requirements: skyfield
version: 1.0.0
license: MIT
"""

from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, Field

_EPHEMERIS = "~/.local/ai-services/almanac/de421.bsp"

_PHASES = [
    (0, 45, "new moon"), (45, 90, "waxing crescent"),
    (90, 135, "first quarter"), (135, 180, "waxing gibbous"),
    (180, 225, "full moon"), (225, 270, "waning gibbous"),
    (270, 315, "last quarter"), (315, 360, "waning crescent"),
]


class Tools:
    class Valves(BaseModel):
        ephemeris_path: str = Field(
            default=_EPHEMERIS, description="Path to the JPL DE421 ephemeris file"
        )

    def __init__(self):
        self.valves = self.Valves()
        self.citation = True
        self._sky = None

    def _ctx(self):
        if self._sky is None:
            from skyfield import almanac
            from skyfield.api import Loader, wgs84
            import os
            load = Loader(os.path.dirname(self.valves.ephemeris_path))
            eph = load(os.path.basename(self.valves.ephemeris_path))
            ts = load.timescale()
            self._sky = (almanac, wgs84, eph, ts)
        return self._sky

    @staticmethod
    def _offset(lon, tz_offset_hours):
        if tz_offset_hours is None:
            return round(lon / 15), True
        return int(tz_offset_hours), False

    def get_sun_times(
        self, lat: float, lon: float, date: str = "", tz_offset_hours: float = None
    ) -> str:
        """
        Sunrise, sunset, and day length for a coordinate and date, computed
        offline. Times are local using the given UTC offset (or a longitude-based
        approximation if omitted — may be off by an hour where DST applies).
        :param lat: Latitude in decimal degrees
        :param lon: Longitude in decimal degrees (negative in the Americas)
        :param date: Date as YYYY-MM-DD (default: today)
        :param tz_offset_hours: Local UTC offset in hours, e.g. -5 for CDT (optional)
        """
        try:
            almanac, wgs84, eph, ts = self._ctx()
        except Exception as e:
            return f"Almanac unavailable (ephemeris load failed): {e}"
        try:
            d = datetime.strptime(date, "%Y-%m-%d") if date else datetime.now()
        except ValueError:
            return f"Bad date '{date}', expected YYYY-MM-DD."
        off, approx = self._offset(lon, tz_offset_hours)
        tz = timezone(timedelta(hours=off))
        day0 = datetime(d.year, d.month, d.day, tzinfo=tz)
        t0, t1 = ts.from_datetime(day0), ts.from_datetime(day0 + timedelta(days=1))
        place = wgs84.latlon(lat, lon)
        times, events = almanac.find_discrete(
            t0, t1, almanac.sunrise_sunset(eph, place))
        rise = set_ = None
        for t, e in zip(times, events):
            local = t.utc_datetime().astimezone(tz)
            if e == 1:
                rise = local
            else:
                set_ = local
        label = f"UTC{off:+d}" + (" (approx from longitude — verify DST)" if approx else "")
        if not rise and not set_:
            return (f"No sunrise or sunset at lat {lat}, lon {lon} on "
                    f"{day0:%Y-%m-%d} (polar day or night).")
        out = [f"Sun at lat {lat}, lon {lon} on {day0:%Y-%m-%d} (times {label}):"]
        if rise:
            out.append(f"- sunrise: {rise:%H:%M}")
        if set_:
            out.append(f"- sunset:  {set_:%H:%M}")
        if rise and set_ and set_ > rise:
            dl = set_ - rise
            out.append(f"- day length: {dl.seconds // 3600} h {dl.seconds % 3600 // 60} min")
        return "\n".join(out)

    def get_moon_info(self, date: str = "") -> str:
        """
        Moon phase and illumination for a date, plus the next full and new
        moons, computed offline.
        :param date: Date as YYYY-MM-DD (default: today)
        """
        try:
            almanac, wgs84, eph, ts = self._ctx()
        except Exception as e:
            return f"Almanac unavailable (ephemeris load failed): {e}"
        try:
            d = datetime.strptime(date, "%Y-%m-%d") if date else datetime.now()
        except ValueError:
            return f"Bad date '{date}', expected YYYY-MM-DD."
        d = d.replace(tzinfo=timezone.utc, hour=12)
        t = ts.from_datetime(d)
        deg = almanac.moon_phase(eph, t).degrees
        frac = almanac.fraction_illuminated(eph, "moon", t)
        name = next(n for a, b, n in _PHASES if a <= deg < b)
        t0, t1 = ts.from_datetime(d), ts.from_datetime(d + timedelta(days=35))
        times, events = almanac.find_discrete(t0, t1, almanac.moon_phases(eph))
        nxt = {}
        for tt, e in zip(times, events):
            if e == 2 and "full" not in nxt:
                nxt["full"] = tt.utc_datetime()
            if e == 0 and "new" not in nxt:
                nxt["new"] = tt.utc_datetime()
        out = [
            f"Moon on {d:%Y-%m-%d}: {name}, {frac:.0%} illuminated.",
            f"- next full moon: {nxt['full']:%Y-%m-%d}" if "full" in nxt else "",
            f"- next new moon:  {nxt['new']:%Y-%m-%d}" if "new" in nxt else "",
        ]
        return "\n".join(x for x in out if x)
