#!/usr/bin/env python3
"""Stream osmium-exported GeoJSONseq POIs into a SQLite database with an R-tree.

Keeps named POIs plus unnamed ones in essential categories (fuel, water,
shelter, medical, ...). Unnamed benches, private pools, parking spaces etc.
are dropped — they'd otherwise dominate the row count.

Usage: poi_load.py pois.geojsonl pois.sqlite
"""
import json
import sqlite3
import sys

KEYS = ("amenity", "shop", "tourism", "leisure", "healthcare", "emergency", "aeroway")

ESSENTIAL = {
    "hospital", "clinic", "doctors", "pharmacy", "fuel", "charging_station",
    "drinking_water", "water_point", "shelter", "toilets", "police",
    "fire_station", "camp_site", "ranger_station", "phone", "emergency_phone",
    "defibrillator", "fire_hydrant", "aerodrome", "ferry_terminal",
    "hunting_stand", "wilderness_hut", "alpine_hut",
}

EXTRA_TAGS = ("opening_hours", "cuisine", "brand", "operator", "phone",
              "addr:street", "addr:housenumber", "addr:city", "addr:state",
              "emergency", "access")


def centroid(geom):
    t = geom.get("type")
    c = geom.get("coordinates")
    if t == "Point":
        return c[0], c[1]
    if t == "Polygon":
        ring = c[0]
    elif t == "MultiPolygon":
        ring = c[0][0]
    else:
        return None
    n = len(ring) - 1 or 1
    return (sum(p[0] for p in ring[:n]) / n, sum(p[1] for p in ring[:n]) / n)


def main():
    src, dst = sys.argv[1], sys.argv[2]
    con = sqlite3.connect(dst)
    con.executescript("""
        PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;
        CREATE TABLE IF NOT EXISTS poi (
            id INTEGER PRIMARY KEY, name TEXT, key TEXT, value TEXT,
            lat REAL, lon REAL, extra TEXT);
        CREATE VIRTUAL TABLE IF NOT EXISTS poi_rtree
            USING rtree(id, min_lat, max_lat, min_lon, max_lon);
    """)
    kept = seen = 0
    batch = []
    for line in open(src, encoding="utf-8", errors="replace"):
        line = line.strip().lstrip("\x1e")
        if not line:
            continue
        seen += 1
        try:
            f = json.loads(line)
        except json.JSONDecodeError:
            continue
        props = f.get("properties") or {}
        key = val = None
        for k in KEYS:
            if props.get(k):
                key, val = k, props[k]
                break
        if not key:
            continue
        name = props.get("name")
        if not name and val not in ESSENTIAL:
            continue
        pt = centroid(f.get("geometry") or {})
        if not pt:
            continue
        lon, lat = pt
        extra = {k: props[k] for k in EXTRA_TAGS if props.get(k)}
        kept += 1
        batch.append((kept, name, key, val, round(lat, 6), round(lon, 6),
                      json.dumps(extra) if extra else None))
        if len(batch) >= 50000:
            con.executemany("INSERT INTO poi VALUES (?,?,?,?,?,?,?)", batch)
            con.executemany(
                "INSERT INTO poi_rtree VALUES (?,?,?,?,?)",
                [(b[0], b[4], b[4], b[5], b[5]) for b in batch])
            con.commit()
            batch = []
            if kept % 1000000 < 50000:
                print(f"{kept:,} kept / {seen:,} seen", flush=True)
    if batch:
        con.executemany("INSERT INTO poi VALUES (?,?,?,?,?,?,?)", batch)
        con.executemany("INSERT INTO poi_rtree VALUES (?,?,?,?,?)",
                        [(b[0], b[4], b[4], b[5], b[5]) for b in batch])
    con.execute("CREATE INDEX IF NOT EXISTS idx_poi_value ON poi(value)")
    con.commit()
    print(f"DONE: {kept:,} POIs kept of {seen:,} features")
    con.close()


if __name__ == "__main__":
    main()
