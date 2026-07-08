"""Retrieval latency across the offline Kiwix library (~370 GB on USB SSD).

Measures full-text search (all books) cold vs warm, plus article fetch time.
Usage: bench_retrieval.py [outfile.jsonl]
"""
import json
import statistics
import sys
import time

import requests

KIWIX = "http://127.0.0.1:8090"
QUERIES = [
    "photosynthesis", "battle of hastings", "insulin resistance",
    "two-stroke engine", "water purification", "supernova",
    "french revolution", "antibiotic resistance", "solar panel wiring",
    "knot tying", "appendicitis symptoms", "compost", "morse code",
    "hypothermia treatment", "cast iron seasoning", "beekeeping",
    "diesel fuel storage", "suture technique", "radio antenna length",
    "edible plants north america",
]
ARTICLES = [
    ("Photosynthesis", "wikipedia_en_all_maxi_2026-02"),
    ("Penicillin", "wikipedia_en_all_maxi_2026-02"),
    ("Hypothermia", "wikipedia_en_all_maxi_2026-02"),
    ("Denali", "wikipedia_en_all_maxi_2026-02"),
    ("Compass", "wikipedia_en_all_maxi_2026-02"),
]


def timed_get(url, **kw):
    t0 = time.time()
    r = requests.get(url, timeout=120, **kw)
    return r, time.time() - t0


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))]


def main():
    out = open(sys.argv[1], "a") if len(sys.argv) > 1 else None
    results = []
    print(f"search latency, {len(QUERIES)} queries x cold+warm (all books):")
    for q in QUERIES:
        rec = {"bench": "retrieval", "query": q}
        for phase in ("cold", "warm"):
            r, dt = timed_get(f"{KIWIX}/search",
                              params={"pattern": q, "pageLength": 5, "format": "xml"})
            n = r.text.count("<item>")
            rec[phase + "_s"] = round(dt, 3)
            rec[phase + "_hits"] = n
        results.append(rec)
        print(f"  {q!r}: cold {rec['cold_s']}s ({rec['cold_hits']} hits), warm {rec['warm_s']}s")
        if out:
            out.write(json.dumps(rec) + "\n")

    print(f"\narticle fetch latency:")
    for title, book in ARTICLES:
        path = title.replace(" ", "_")
        r, dt = timed_get(f"{KIWIX}/content/{book}/A/{path}", allow_redirects=True)
        if r.status_code == 404:
            r, dt = timed_get(f"{KIWIX}/content/{book}/{path}", allow_redirects=True)
        rec = {"bench": "article_fetch", "title": title,
               "seconds": round(dt, 3), "status": r.status_code,
               "kbytes": round(len(r.content) / 1024)}
        results.append(rec)
        print(f"  {title}: {rec['seconds']}s, HTTP {r.status_code}, {rec['kbytes']} KB")
        if out:
            out.write(json.dumps(rec) + "\n")

    colds = [r["cold_s"] for r in results if "cold_s" in r]
    warms = [r["warm_s"] for r in results if "warm_s" in r]
    summary = {
        "bench": "retrieval_summary",
        "n_queries": len(colds),
        "cold_median_s": round(statistics.median(colds), 3),
        "cold_p90_s": round(pct(colds, 90), 3),
        "warm_median_s": round(statistics.median(warms), 3),
        "warm_p90_s": round(pct(warms, 90), 3),
    }
    print("\nsummary:", json.dumps(summary, indent=1))
    if out:
        out.write(json.dumps(summary) + "\n")
        out.close()


if __name__ == "__main__":
    main()
