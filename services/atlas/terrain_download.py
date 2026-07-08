#!/usr/bin/env python3
"""Download Mapzen terrarium elevation tiles into an MBTiles archive.

Coverage: global z0-9, North America (lat 7..75, lon -170..-50) z10-12.
Resumable: already-stored tiles are skipped on restart.
Run with the valhalla venv python (needs requests).
"""
import math
import queue
import sqlite3
import sys
import threading
import time

import requests

DB = sys.argv[1] if len(sys.argv) > 1 else "~/.local/ai-services/atlas/terrain.mbtiles"
URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
GLOBAL_MAXZ = 9
NA_ZOOMS = (10, 11, 12)
NA = {"min_lat": 7.0, "max_lat": 75.0, "min_lon": -170.0, "max_lon": -50.0}
THREADS = 40


def lonlat_to_tile(lon, lat, z):
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    lat_r = math.radians(lat)
    y = int((1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n)
    return max(0, min(n - 1, x)), max(0, min(n - 1, y))


def tile_list():
    tiles = []
    for z in range(0, GLOBAL_MAXZ + 1):
        n = 2 ** z
        for x in range(n):
            for y in range(n):
                tiles.append((z, x, y))
    for z in NA_ZOOMS:
        x0, y0 = lonlat_to_tile(NA["min_lon"], NA["max_lat"], z)
        x1, y1 = lonlat_to_tile(NA["max_lon"], NA["min_lat"], z)
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                tiles.append((z, x, y))
    return tiles


def main():
    con = sqlite3.connect(DB)
    con.executescript(
        """
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS metadata (name TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS tiles (
            zoom_level INTEGER, tile_column INTEGER, tile_row INTEGER,
            tile_data BLOB,
            PRIMARY KEY (zoom_level, tile_column, tile_row)
        );
        """
    )
    meta = {
        "name": "Terrarium elevation",
        "format": "png",
        "type": "baselayer",
        "version": "1",
        "description": "Mapzen terrarium terrain tiles: global z0-9, North America z10-12",
        "minzoom": "0",
        "maxzoom": str(max(NA_ZOOMS)),
        "bounds": "-180,-85.0511,180,85.0511",
        "attribution": "Mapzen terrain tiles (AWS Open Data); USGS 3DEP, SRTM, GMTED, ETOPO1",
    }
    for k, v in meta.items():
        con.execute("INSERT OR REPLACE INTO metadata VALUES (?,?)", (k, v))
    con.commit()

    todo = tile_list()
    total = len(todo)
    have = {
        (z, x, y)
        for z, x, y in con.execute("SELECT zoom_level, tile_column, tile_row FROM tiles")
    }
    # tiles table stores TMS-flipped rows; compare in flipped space
    todo = [(z, x, y) for z, x, y in todo if (z, x, (2 ** z - 1) - y) not in have]
    print(f"total {total} tiles, {len(have)} present, {len(todo)} to fetch", flush=True)

    q = queue.Queue(maxsize=4000)
    results = queue.Queue(maxsize=4000)
    failures = []

    def worker():
        s = requests.Session()
        while True:
            item = q.get()
            if item is None:
                return
            z, x, y = item
            for attempt in range(5):
                try:
                    r = s.get(URL.format(z=z, x=x, y=y), timeout=60)
                    if r.status_code == 200:
                        results.put((z, x, (2 ** z - 1) - y, r.content))
                        break
                    if r.status_code == 404:
                        break  # no tile here; skip
                except requests.RequestException:
                    pass
                time.sleep(2 * (attempt + 1))
            else:
                failures.append((z, x, y))

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(THREADS)]
    for t in threads:
        t.start()

    feeder_done = threading.Event()

    def feeder():
        for item in todo:
            q.put(item)
        for _ in threads:
            q.put(None)
        feeder_done.set()

    threading.Thread(target=feeder, daemon=True).start()

    written = 0
    t0 = time.time()
    while True:
        try:
            z, x, row, data = results.get(timeout=5)
            con.execute(
                "INSERT OR REPLACE INTO tiles VALUES (?,?,?,?)", (z, x, row, data)
            )
            written += 1
            if written % 2000 == 0:
                con.commit()
                rate = written / (time.time() - t0)
                eta = (len(todo) - written) / rate / 3600 if rate else 0
                print(
                    f"{written}/{len(todo)} written, {rate:.0f} tiles/s, eta {eta:.2f} h",
                    flush=True,
                )
        except queue.Empty:
            if feeder_done.is_set() and all(not t.is_alive() for t in threads):
                break
    con.commit()
    con.close()
    print(f"DONE: {written} written, {len(failures)} failures", flush=True)
    if failures:
        print("failed tiles:", failures[:50], flush=True)


if __name__ == "__main__":
    main()
