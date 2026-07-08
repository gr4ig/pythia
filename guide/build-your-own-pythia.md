# Build Your Own Pythia

## A field guide to assembling a fully offline AI knowledge system

This is the recipe behind Pythia — the AI Data Center in a Backpack. Everything
below uses open-source software and freely distributed data. You can follow it
exactly and get what we got, or treat each phase as a module and adapt it to
your hardware, your region, and your storage budget. Adaptation notes follow
every phase.


> **Working code for everything below:** [github.com/gr4ig/pythia](https://github.com/gr4ig/pythia) —
> every service script, LLM tool, the benchmark harness, and the ops tooling,
> exactly as we run them. Clone it and follow along, or fork it and make it
> yours.

Two ground rules before you start, both learned the hard way:

1. **Storage has a grain.** Static data — wiki archives, map tiles — streams
   beautifully from cheap external USB storage. Anything that fsyncs (live
   search indexes, SQLite under write load) belongs on internal SSD/NVMe. Our
   geocoder was *unable to start* from a USB drive (10–16 s per sync write) and
   started in 5 seconds from internal storage. Respect the grain and every
   phase below just works.
2. **Verify behavior, not exit codes.** Three of our worst bugs — a routing
   database that silently lost every street name, a download that silently
   restarted from zero, a benchmark that flattered the wrong configuration —
   all reported success. Each phase below ends with a verification step. Do
   them.

macOS-specific note: Apple's privacy layer (TCC) blocks or *silently hangs*
background services accessing external drives until each binary is approved
once. If a service works from your terminal but hangs under launchd, that's
TCC — approve the permission prompt or grant the binary Full Disk Access.
Linux users skip this entire class of problem.

---

## Choose your tier

| Tier | Adds | Disk | Download | What you get |
|---|---|---|---|---|
| **1 — Librarian** | LLM + chat UI + offline wiki library | 150–250 GB | ~150 GB | Ask questions, get cited answers from Wikipedia + reference works |
| **2 — Navigator** | geocoding, routing, places, almanac | +200 GB | +100 GB | "How far, what's near me, when's sunset" — computed, not recalled |
| **3 — Pythia-class** | planet map display, terrain, voice, benchmarks | +450 GB | +300 GB | The full system: a spoken question to a spoken, tool-verified answer in ~16 s |

**Hardware floor:** any machine that runs a 7–12B parameter model comfortably —
16 GB RAM minimum, 32+ GB recommended. We used an Apple M5 Pro with 48 GB RAM
and a 4 TB USB SSD (~$300); an x86 Linux box with a mid-range GPU works the
same way, minus the TCC pain. All software below runs on macOS and Linux.

---

## Phase 1 — The AI layer

**Install [Ollama](https://ollama.com)** and pull models sized to your RAM:

| RAM | Suggested class | Our measured throughput (M5 Pro) |
|---|---|---|
| 16 GB | 4–8B (e.g. small Gemma/Qwen/Llama variants) | 115–192 tok/s on our e2b/e4b models |
| 32 GB | 12–27B | 78 tok/s on gemma4:26b — our workhorse |
| 48+ GB | 27–35B | 80 tok/s on qwen3.6:35b |

The model must support **native tool calling** through Ollama — test it before
building anything else (send a `/api/chat` request with a `tools` array; you
want a `tool_calls` response, not prose about tools).

**Install [Open WebUI](https://openwebui.com)** as the front end. Everything in
this guide plugs into it as a custom Tool — a plain Python class with typed
methods. Tools are pasted into the UI (Workspace → Tools) or inserted into its
SQLite database; either works.

**Voice (Tier 3, optional):** [whisper.cpp](https://github.com/ggerganov/whisper.cpp)
with the `large-v3-turbo` model (1.5 GB) for ears — we measured ~0.3 s per
spoken question — and [Kokoro](https://github.com/thewh1teagle/kokoro-onnx)
(337 MB, ONNX) for voice, 1–5 s per answer. Both need thin adapter servers
exposing OpenAI-compatible endpoints (`/v1/audio/transcriptions`,
`/v1/audio/speech`) so Open WebUI can use them; each adapter is ~50 lines of
FastAPI.

*Adapt:* any OpenAI-compatible local stack works — llama.cpp server, vLLM,
LM Studio. The recipe only assumes an LLM endpoint with tool calling and a
chat UI with a custom-tool mechanism.

---

## Phase 2 — The library (Tier 1)

**Source:** [library.kiwix.org](https://library.kiwix.org) — hundreds of
compressed, indexed, self-contained website snapshots (ZIM files).
**Server:** `kiwix-serve` from [kiwix-tools](https://github.com/kiwix/kiwix-tools)
(we used 3.8.2) serves any number of ZIMs with full-text search across all of
them in one query.

Our 35-book, 463 GiB selection, as a starting menu:

- **Core reference (152 GiB):** Wikipedia complete-with-images (124 GB),
  Wiktionary, Wikisource, Wikibooks, Wikispecies, Wikiversity, Wikiquote,
  Wikivoyage, WikiMed
- **Literature (221 GiB):** Project Gutenberg — ~70,000 books
- **Technical (97 GiB):** Stack Overflow complete (80 GB), Math/Physics/
  Electronics/Unix/SuperUser/AskUbuntu Stack Exchanges, DevDocs, Arch wiki
- **Practical (14 GiB):** iFixit repair guides, MedlinePlus, Ready.gov,
  Home Improvement + Gardening + Cooking SE, Appropedia, Energypedia,
  post-disaster references

**Downloads at this scale need a resume-safe loop.** `curl --retry` combined
with `-C -` computes its resume offset *once per invocation* — a mid-transfer
retry silently truncates your progress (we lost 7 GB learning this). Use an
outer loop so every attempt recomputes the offset:

```sh
until curl -sS -L -C - -o "$FILE" "$URL"; do
  echo "resuming at $(stat -c %s "$FILE" 2>/dev/null || stat -f %z "$FILE") bytes"
  sleep 20
done
```

**Serve from a path list, not a directory glob** (this is the TCC-proof
pattern, and it's cleaner everywhere): keep a plain-text file listing one ZIM
path per line, and have your service script pass those paths to `kiwix-serve`.
Adding a book = append a line, restart the service.

**Wire it to the LLM** with an Open WebUI tool ([`services/kiwix/`](https://github.com/gr4ig/pythia/tree/main/services/kiwix) in the repo) exposing three functions:
`list_books()`, `search(query)` (kiwix-serve's `/search?pattern=…&format=xml`
across all books), and `get_article(title, book)` (fetch, strip HTML, truncate
to ~12K chars). Two gotchas from our build: pass raw bytes to your HTML parser
so charset sniffing works (avoids mojibake), and Gutenberg's search suggestions
point at *cover* pages — rewrite `Title_cover.N` paths to `Title.N`.

**Verify:** time a full-library search. Ours: 1.9 s cold, 0.12 s warm, across
463 GiB on USB. If you're dramatically slower, check that the ZIMs' embedded
indexes are intact (re-download, don't trust a partial file).

*Adapt:* this is the most budget-elastic phase. Wikipedia's `nopic` variant
saves ~70 GB. Skip Gutenberg and Stack Overflow and Tier 1 fits in ~60 GB.
Every ZIM is independent — take what serves your mission.

---

## Phase 3 — Geographic computation (Tier 2)

The organizing insight of the whole build: text knowledge is *storage*;
geographic knowledge is *computation*. A model can recall roughly where Sedona
is. It cannot know it's 47 km from Flagstaff by road — ours confidently said
177 — unless something computes it.

### 3a. Geocoding — place names ↔ coordinates

**[Photon](https://github.com/komoot/photon)** (we used 1.2.1; needs Java 21+).
Prebuilt planet index: `https://download1.graphhopper.com/public/photon-db-planet-1.0-latest.tar.bz2`
— 61 GB compressed, ~90 GB extracted, 286M places, rebuilt weekly.

Our serve script, LLM tool, and installer: [`services/photon/`](https://github.com/gr4ig/pythia/tree/main/services/photon). Three rules from our build:

1. **The live index goes on internal storage.** Photon runs an embedded
   OpenSearch node; on our USB SSD every cluster-state fsync took 10–16 s and
   startup timed out on every attempt. Internal NVMe: 5-second startup. Keep
   the compressed archive on external storage for re-extraction.
2. **Query with `lang=en`** (or your language). Default local-language ranking
   put a Canadian mountain named "Eiffel Tower" above the Paris landmark and
   returned Tokyo as 東京都.
3. Extract with a parallel bzip2 (`pbzip2`/`lbzip2`) — it's the difference
   between 30 minutes and several hours.

*Adapt:* graphhopper also publishes **country extracts** — if planet-scale
is too much, a single-country Photon index can be under 5 GB.

### 3b. Routing — turn-by-turn, offline

**[Valhalla](https://github.com/valhalla/valhalla)** built from an OSM extract
([Geofabrik](https://download.geofabrik.de) publishes daily continent/country/
region files). Our North America build: 18 GB extract → 25 GB of routing tiles
in **33 minutes** at 14 threads (48 GB RAM was ample).

On macOS, install via the **pyvalhalla-weekly** Python wheels (the stable wheel
crashes with SIGBUS on continent-scale builds — a 512 KB worker-thread stack
overflow fixed only in weekly builds). Linux users can use distro packages or
Docker.

**The critical rule: never resume an interrupted tile build.** A resumed build
completes "successfully" with every street name silently missing — routes and
distances correct, every instruction pointing at nothing. The only symptom is
one `osmdata_counts.bin` error line deep in the log. Always rebuild all stages
in one invocation, and grep the build log before trusting the output.

Our tool: [`services/valhalla/`](https://github.com/gr4ig/pythia/tree/main/services/valhalla). **Verify with names, not just status codes:** request a route and check the
turn instructions contain actual street names ("Turn left onto **Main Street**"),
in your region and across any borders your extract includes.

*Adapt:* pick your extract by region — a US state builds in minutes on modest
hardware; the planet needs ~64 GB+ RAM and patience. The Open WebUI tool is
~150 lines: `get_route(start, end, mode)` and `compare_travel_modes(...)`
against Valhalla's `/route` endpoint.

### 3c. Places — "nearest hospital / gas / campground"

Extract points of interest from the **same OSM file** you used for routing:

```sh
osmium tags-filter region.osm.pbf \
  nwr/amenity nwr/shop nwr/tourism nwr/leisure \
  nwr/healthcare nwr/emergency nwr/aeroway=aerodrome \
  -o pois.osm.pbf
osmium export pois.osm.pbf -f geojsonseq -o pois.geojsonl \
  --geometry-types=point,polygon
```

Stream the GeoJSON into SQLite: one `poi` table (name, category key/value,
lat, lon, useful extra tags as JSON) plus an R-tree index on the coordinates.
Two filters that matter: **drop unnamed features unless they're essential
categories** (unnamed fuel, water, shelters stay; unnamed benches and private
swimming pools — millions of them — go), and **rank category matches above
name matches** (or "hospital" returns veterinary hospitals before the actual
ER, as ours did on the first pass). Our North America result: 11.2M features
filtered to 4.19M POIs in an 808 MB database.

The loader and query tool: [`services/poi/`](https://github.com/gr4ig/pythia/tree/main/services/poi). The query tool: R-tree bounding-box prefilter → haversine distance → sort by
(match-rank, distance), with a synonym map from plain words ("gas station",
"urgent care", "campground") to OSM tags.

### 3d. Almanac — sun and moon, forever

The best value-per-gigabyte in the entire system: **[Skyfield](https://rhodesmill.org/skyfield/)**
plus the JPL DE421 ephemeris — a 17 MB file valid for decades. Sunrise, sunset,
day length, moon phase, next full/new moon, for any coordinates and any date,
computed in milliseconds ([`services/almanac/`](https://github.com/gr4ig/pythia/tree/main/services/almanac)). Verify against published sun times for your city;
ours matched to the minute.

---

## Phase 4 — Maps you can see (Tier 3)

Models use coordinates; humans want a map. Both halves below are static files
served by one small Go binary — they stream perfectly from USB.

**Base map:** [Protomaps](https://protomaps.com) publishes free daily planet
builds (`https://build.protomaps.com/YYYYMMDD.pmtiles`, ~137 GB, zoom 0–15).
Serve with [go-pmtiles](https://github.com/protomaps/go-pmtiles) (`pmtiles
serve <dir> --cors "*"` — it picks up every archive in the directory). Display
with [MapLibre GL JS](https://maplibre.org) + the `@protomaps/basemaps` style
package + the protomaps-assets fonts and sprites — **all hosted locally**; a
truly offline map page can't lean on a single CDN. Bonus: wire the page's
search box to your Photon instance and you have a searchable offline atlas.

**Terrain:** the [AWS Terrain Tiles](https://registry.opendata.aws/terrain-tiles/)
open dataset — ready-made "terrarium" elevation PNGs, no GDAL processing.
Elevation decodes from pixel color: `(R×256 + G + B/256) − 32768` meters.
Our coverage strategy, adaptable to any region: **global at zoom 0–9**
(~300 m resolution) plus **your region at zoom 10–12** (40–80 m; US areas
derive from 10 m USGS data). That was 2.58M tiles / 144 GB for all of North
America — a single US state at deep zoom is a few GB. Download into MBTiles
(SQLite — build it on internal storage), convert with `pmtiles convert`, park
the result next to the basemap. The same tiles power three things: hillshade
on the map, client-side contour lines ([maplibre-contour](https://github.com/onthegomap/maplibre-contour)),
and a `get_elevation(lat, lon)` tool for the model. Elevation data never needs
refreshing — mountains don't move.

Our atlas page, terrain downloader, and elevation tool: [`services/atlas/`](https://github.com/gr4ig/pythia/tree/main/services/atlas) (run [`scripts/fetch-assets.sh`](https://github.com/gr4ig/pythia/blob/main/scripts/fetch-assets.sh) for the web libraries). Verify against ground truth: our checks — Mt. Whitney 4412 m (actual 4421),
Death Valley −81 m, Denver 1597 m — all landed within the tile resolution.

---

## Phase 5 — Making the model use it all

Each capability becomes an Open WebUI tool: a Python class with docstringed,
type-hinted methods (the docstrings become the tool schema the model sees).
All six of ours, with installers, are in the repo's `services/` directories, and the chaining skill is [`openwebui/`](https://github.com/gr4ig/pythia/tree/main/openwebui). Ours, as a checklist: wiki search/fetch, geocode/reverse-geocode, route,
elevation + profile, places-nearby, sun/moon. Keep result strings compact and
information-dense — they're going into a context window.

Two integration lessons:

- **Description quality is tool-selection quality.** Say *when* to use each
  tool, and state coverage limits in the description ("North America only")
  so the model doesn't attempt Paris-to-Berlin routing.
- **Teach chaining explicitly.** The magic is composition — geocode two names,
  route between the coordinates, check terrain along the way. A skill or
  system-prompt section listing these patterns ("nearest hospital to X →
  geocode X, then places-nearby") took our model from tools-that-fire to
  tools-that-chain. Include the coordinate convention (negative longitude in
  the Americas) — it prevents a whole class of silent errors.

---

## Phase 6 — Prove it works (don't skip this)

The complete harness — agent loop, graders, question sets — is [`bench/`](https://github.com/gr4ig/pythia/tree/main/bench). Our first benchmark said tools made the model *worse* — 87% with tools versus
100% without. Both numbers were artifacts, and finding out why taught us more
than a clean run would have:

- **The agent loop needs two guardrails:** refuse duplicate tool calls, and
  force a final answer on the last round. Without them, our model re-searched
  the wiki for facts it already knew — one question burned 938 seconds.
- **The question set must be guess-proof.** A capable model already knows
  Chernobyl's year and rough intercity distances. Derive gold answers *from
  your own offline services* with tight tolerances: distance between mid-size
  towns (±5%), elevation at raw coordinates, the *name* of the nearest
  facility, sunrise to the minute on a specific date.

With both fixed, the honest result: on common knowledge, tools changed nothing
(46/47 both ways). On the guess-proof set: bare model **3/10** with confident
hallucinations, tools **10/10**. Median answer cost: 2.3 s bare, 10.6 s with
tools. That table — not the feature list — is the proof your build works.

---

## Phase 7 — Keeping it alive

| Source | Upstream cadence | Sensible refresh |
|---|---|---|
| ZIM library | monthly-ish per book | quarterly, selectively |
| Photon index | weekly | quarterly |
| OSM extract → routing tiles + POI db | daily | quarterly (rebuild both from one download) |
| Protomaps basemap | daily | quarterly |
| Terrain | never | never |

Staleness is cheap for reference knowledge — a quarterly ~350–400 GB refresh
keeps the system within three months of the live world. Ours are [`ops/`](https://github.com/gr4ig/pythia/tree/main/ops) in the repo — two scripts worth
adopting on day one: a **refresh script** (per-source: download → verify →
swap → roll back on failure; every swap keeps the old data until the new data
proves itself) and a **clone script** (rsync of services + data to a spare
drive — our full system replicates in an afternoon). Put the refresh on a
calendar; entropy doesn't send reminders.

---

## Phase 8 — Memory and agency (optional, but it changes what you have)

Everything so far makes the system *knowledgeable*. Two more pieces make it a
colleague rather than a reference desk:

**A brain for derived content.** The library holds what humanity knows; give
your system a place to file what *it* figures out. Ours is a plain
[Obsidian](https://obsidian.md) vault in PARA structure (Inbox / Areas /
Projects / Resources / Archives), with a file standard (Markdown + YAML
frontmatter: title, created, tags, status, description) written into an Open
WebUI skill so the model files things correctly on its own. The write path is
Open WebUI's terminal integration pinned to the vault directory; the read path
is you, in Obsidian. Research reports, trip plans, syntheses — they accumulate
into a knowledge garden the static library can never contain, because it's
about *your* questions.

**An offline coding agent.** [OpenCode](https://opencode.ai) provides a
Claude Code-style agentic coding environment that runs against local models.
Point it at your Ollama endpoint in `~/.config/opencode/opencode.json`:

```json
{
  "provider": {
    "ollama": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Ollama (local)",
      "options": { "baseURL": "http://localhost:11434/v1" },
      "models": { "your-model:tag": { "name": "Your Model" } }
    }
  },
  "model": "ollama/your-model:tag"
}
```

With these two, the build completes a triad worth naming: **cognition** (the
models), **memory** (a vault that grows), and **agency** (an agent that can
write and run code) — all with the network cable unplugged.

## Bill of materials (our build, for calibration)

| Component | Size | Source cost |
|---|---|---|
| Laptop (Apple M5 Pro, 48 GB) | — | consumer hardware |
| 4 TB external USB SSD | — | ~$300 class |
| Wiki library (35 ZIMs) | 463 GiB | free |
| LLM weights (5 models) | 100 GiB | free |
| Photon planet index | 88 GiB live + 57 archive | free |
| Valhalla NA tiles + extract | 40 GiB | free |
| Protomaps planet basemap | 137 GB | free |
| Terrain (global + NA deep) | 144 GB | free |
| POI database | 0.8 GB | free |
| Ephemeris, speech models, glue | ~2 GB | free |
| **Total** | **~1.05 TiB** | **$0 software** |

Build time: roughly three days of wall clock, most of it downloads. Measured
end-to-end: spoken question → tool-verified spoken answer, median 15.8 s.

## Attribution obligations

Your build inherits its data's licenses: OpenStreetMap data (routing, POI,
geocoding, basemap) is ODbL — attribute "© OpenStreetMap contributors";
Wikipedia/Wikimedia content is CC BY-SA; terrain tiles compose USGS 3DEP,
SRTM, GMTED, and ETOPO1 (attribute per the AWS dataset page); Project
Gutenberg texts are public domain with trademark rules on redistribution.
Attribution strings in your map UI and tool citations cover the common cases.

---

*This guide documents the build described in "AI Data Center in a Backpack,
Parts 1–2." All code lives at [github.com/gr4ig/pythia](https://github.com/gr4ig/pythia). Follow it
verbatim or fork it freely — the entire point of a backpack data center is
that it's yours.*
