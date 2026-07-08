# Pythia — an AI Data Center in a Backpack

The working code behind **Pythia the Polymath**: a fully offline AI knowledge
system built on one consumer laptop and one external SSD. A local LLM with a
voice, ~463 GiB of searchable reference material (Wikipedia, Gutenberg, Stack
Overflow, and more), and live geographic computation — geocoding, routing,
points of interest, elevation, and an astronomical almanac — with **zero
network access at question time**.

Measured, not promised: on questions whose answers can't be memorized, the
bare model scored 3/10 with confident hallucinations; with these tools, 10/10.
Median spoken-question-to-spoken-answer: 15.8 seconds. The benchmark harness
that produced those numbers is in this repo — run it on your own build.

**Start with [`guide/build-your-own-pythia.md`](guide/build-your-own-pythia.md).**
It's the full recipe — hardware tiers from a 150 GB "Librarian" build up to
the ~1 TiB full system — with exact sources, sizes, timings, and the failure
modes we hit so you don't have to. This repo is its companion: every script
and tool the guide describes, as we actually run them.

Background reading: the *AI Data Center in a Backpack* paper series at
[gr4ig.substack.com](https://gr4ig.substack.com).

## Repository map

```
guide/      The Build-Your-Own guide (start here)
services/   One directory per capability:
  kiwix/      offline wiki library — serve script, library rescan, LLM tool
  photon/     geocoding (place name ↔ coordinates) — serve script, LLM tool + installer
  valhalla/   routing (North America in our build) — serve script, LLM tool
  atlas/      map display + terrain — tile/web serve scripts, MapLibre page,
              terrain tile downloader, elevation LLM tool + installer
  poi/        points of interest — OSM extractor/loader, LLM tool + installer
  almanac/    sun & moon — Skyfield LLM tool + installer
ops/        pythia-refresh.sh (quarterly data updates, verify + rollback)
            pythia-clone.sh (replicate the whole system to a spare drive)
bench/      The benchmark harness: retrieval latency, model throughput,
            tools-on/off answer quality, full voice-loop timing
launchd/    macOS service definitions (Linux users: systemd units are a
            straightforward translation — each runs one serve script)
openwebui/  The "skill" that teaches the model to chain the tools
scripts/    fetch-assets.sh — downloads third-party web libraries and the
            JPL ephemeris that we don't redistribute
```

## Conventions you'll want to adapt

- **`/Volumes/PYTHIA_SSD`** is the placeholder for the external drive holding
  bulk data (ZIMs, map tiles, archives). Set yours with a find-and-replace.
- **`~/.local/ai-services/`** is where services and *live databases* live —
  on internal storage, deliberately. Rule of thumb from hard experience:
  static data streams fine from USB; anything that fsyncs (the Photon index,
  SQLite under write load) must be on internal SSD/NVMe.
- **LLM tools** (`openwebui_tool.py` files) are [Open WebUI](https://openwebui.com)
  custom tools. Paste them into Workspace → Tools, or use the `install_*.py`
  scripts for direct database registration. The classes are plain Python —
  porting them to another tool-calling frontend is mostly deleting the
  Valves boilerplate.
- **Third-party assets are fetched, not vendored:** run
  `scripts/fetch-assets.sh` after cloning to pull MapLibre GL, the Protomaps
  basemap styles/fonts/sprites, maplibre-contour, and the DE421 ephemeris.

## Data licenses your build inherits

OpenStreetMap-derived data (geocoding, routing, POI, basemap) is
[ODbL](https://www.openstreetmap.org/copyright) — attribute
"© OpenStreetMap contributors". Wikimedia content is CC BY-SA. Terrain tiles
compose USGS 3DEP, SRTM, GMTED and ETOPO1 (see the
[AWS Terrain Tiles](https://registry.opendata.aws/terrain-tiles/) page).
Project Gutenberg texts are public domain with trademark conditions.

## License

Code in this repository: MIT (see LICENSE). The guide text:
CC BY-SA 4.0.

---

*Written with the Gr4Ig AI agent team, a multi-agent system leveraging a
variety of large language models.*
