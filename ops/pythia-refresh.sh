#!/bin/zsh
# pythia-refresh.sh — keep Pythia, the offline polymath's data sources current.
#
#   pythia-refresh.sh              interactive: show freshness, ask what to update
#   pythia-refresh.sh status       report installed vs upstream, no downloads
#   pythia-refresh.sh update X     X = photon | protomaps | valhalla | poi | kiwix | all
#
# Run from Terminal (or the Desktop launcher), NOT from a background service:
# macOS privacy controls block background processes from the SSD. If macOS
# asks to allow access to files on a removable volume, click Allow.
#
# Terrain tiles are deliberately absent: elevation data doesn't change.

set -u
SSD="/Volumes/PYTHIA_SSD"
AI="$HOME/.local/ai-services"
STATE="$AI/pythia-refresh.state"
PHOTON_URL="https://download1.graphhopper.com/public/photon-db-planet-1.0-latest.tar.bz2"
GEOFABRIK_URL="https://download.geofabrik.de/north-america-latest.osm.pbf"
PROTOMAPS_BASE="https://build.protomaps.com"
UID_=$(id -u)

# ---------- helpers ----------
die() { echo "ERROR: $*" >&2; exit 1 }

state_get() { grep "^$1=" "$STATE" 2>/dev/null | tail -1 | cut -d= -f2 }
state_set() {
  grep -v "^$1=" "$STATE" 2>/dev/null > "$STATE.tmp" || true
  echo "$1=$2" >> "$STATE.tmp"
  mv "$STATE.tmp" "$STATE"
}

http_last_modified() {  # -> YYYY-MM-DD or empty
  curl -sI --max-time 30 "$1" | grep -i '^last-modified' \
    | sed 's/^[^:]*: //' | tr -d '\r' \
    | xargs -I{} date -jf "%a, %d %b %Y %T %Z" {} +%Y-%m-%d 2>/dev/null
}

resume_download() {  # url dest — survives drops without truncating progress
  local url="$1" dest="$2" tries=0
  until curl -sS -L -C - -o "$dest" --max-time 21600 "$url"; do
    (( tries++ ))
    (( tries > 60 )) && return 1
    echo "  ...download interrupted at $(stat -f %z "$dest" 2>/dev/null || echo 0) bytes, resuming in 20s"
    sleep 20
  done
}

geofabrik_date() {  # -latest redirects to north-america-YYMMDD.osm.pbf
  curl -sI --max-time 30 "$GEOFABRIK_URL" | grep -i '^location' \
    | grep -oE '[0-9]{6}' | head -1 | sed -E 's/^(..)(..)(..)$/20\1-\2-\3/'
}

latest_protomaps_build() {  # probe today backwards for newest daily build
  local d code
  for i in $(seq 0 10); do
    d=$(date -v-${i}d +%Y%m%d)
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 20 -I "$PROTOMAPS_BASE/$d.pmtiles")
    [[ "$code" == "200" ]] && { echo "$d"; return 0 }
  done
  return 1
}

check_ssd() {
  [[ -d "$SSD" ]] || die "SSD not mounted at $SSD"
  ls "$SSD" >/dev/null 2>&1 || die "macOS denied access to $SSD — run from Terminal (which has Full Disk Access) and click Allow if prompted."
}

service_up() {  # name url — poll up to N seconds
  local url="$1" secs="${2:-120}"
  for i in $(seq 1 $((secs / 5))); do
    curl -s -o /dev/null --max-time 5 "$url" && return 0
    sleep 5
  done
  return 1
}

# ---------- status ----------
cmd_status() {
  echo "=== Pythia data freshness ($(date +%Y-%m-%d)) ==="
  echo
  echo "photon (geocoder index, 61 GB download):"
  echo "  installed: $(state_get photon)"
  echo "  upstream:  $(http_last_modified "$PHOTON_URL") (weekly builds)"
  echo
  echo "protomaps (basemap, ~137 GB download):"
  echo "  installed: $(state_get protomaps)"
  echo "  upstream:  $(latest_protomaps_build || echo unknown) (daily builds)"
  echo
  echo "valhalla (routing, 18 GB download + ~45 min rebuild):"
  echo "  installed: $(state_get valhalla)"
  echo "  upstream:  $(geofabrik_date) (daily extracts)"
  echo
  echo "kiwix (wikis, ~370 GB total):"
  echo "  installed ZIMs and their build dates:"
  sed -e 's/.*\///' -e 's/\.zim$//' "$AI/kiwix/zims.list" 2>/dev/null | sed 's/^/    /'
  echo "  upstream: browse https://library.kiwix.org (most ZIMs rebuild monthly-quarterly)."
  echo "  To update: download newer ZIMs to the SSD (see $AI/kiwix/download-zims.sh),"
  echo "  then 'update kiwix' here (or the Refresh Kiwix Library launcher) to rescan."
  echo
  echo "poi (places database, rebuilt from the valhalla extract):"
  echo "  installed: $(state_get poi) — rebuild with 'update poi' after a valhalla update"
  echo
  echo "terrain: static by design — never needs refreshing."
}

# ---------- photon ----------
cmd_update_photon() {
  echo "=== Photon: download new planet index ==="
  check_ssd
  local avail=$(df -g "$HOME" | awk 'NR==2 {print $4}')
  (( avail < 120 )) && die "need ~120 GB free on internal disk for extraction, have ${avail} GB"
  local arch="$SSD/photon/photon-db-planet-1.0-latest.tar.bz2"
  echo "downloading (~61 GB, resumable)..."
  rm -f "$arch.new"
  resume_download "$PHOTON_URL" "$arch.new" || die "download failed"
  echo "extracting to internal staging (~30 min)..."
  rm -rf "$AI/photon/photon_data.new"
  mkdir -p "$AI/photon/photon_data.new"
  ( cd "$AI/photon/photon_data.new" && pbzip2 -cd "$arch.new" | tar x --strip-components 1 -f - photon_data ) \
    || { rm -rf "$AI/photon/photon_data.new"; die "extraction failed" }
  echo "swapping service..."
  launchctl unload ~/Library/LaunchAgents/local.photon.plist 2>/dev/null
  mv "$AI/photon/photon_data" "$AI/photon/photon_data.old"
  mv "$AI/photon/photon_data.new" "$AI/photon/photon_data"
  launchctl load ~/Library/LaunchAgents/local.photon.plist
  if service_up "http://127.0.0.1:2322/api?q=paris&limit=1" 300; then
    rm -rf "$AI/photon/photon_data.old"
    mv "$arch.new" "$arch"
    state_set photon "$(http_last_modified "$PHOTON_URL")"
    echo "photon OK — new index live on port 2322."
  else
    echo "new index failed to start — ROLLING BACK" >&2
    launchctl unload ~/Library/LaunchAgents/local.photon.plist 2>/dev/null
    rm -rf "$AI/photon/photon_data"
    mv "$AI/photon/photon_data.old" "$AI/photon/photon_data"
    launchctl load ~/Library/LaunchAgents/local.photon.plist
    die "photon update rolled back; old index restored. Check $AI/photon/logs/"
  fi
}

# ---------- protomaps ----------
cmd_update_protomaps() {
  echo "=== Protomaps: download new planet basemap ==="
  check_ssd
  local build=$(latest_protomaps_build) || die "no recent build found upstream"
  [[ "$build" == "$(state_get protomaps)" ]] && { echo "already on newest build $build"; return }
  local dest="$SSD/protomaps/planet.pmtiles"
  echo "downloading build $build (~137 GB, resumable)..."
  resume_download "$PROTOMAPS_BASE/$build.pmtiles" "$dest.new" || die "download failed"
  pmtiles show "$dest.new" >/dev/null 2>&1 || die "downloaded archive fails verification, keeping old basemap"
  mv -f "$dest.new" "$dest"
  launchctl kickstart -k "gui/$UID_/local.pmtiles"
  sleep 3
  curl -s -o /dev/null --max-time 20 "http://127.0.0.1:8096/planet/0/0/0.mvt" \
    || die "tile server not answering after swap — check $AI/atlas/logs/"
  state_set protomaps "$build"
  echo "protomaps OK — atlas now serving build $build."
}

# ---------- valhalla ----------
cmd_update_valhalla() {
  echo "=== Valhalla: download new OSM extract and rebuild tiles ==="
  check_ssd
  local avail=$(df -g "$HOME" | awk 'NR==2 {print $4}')
  (( avail < 80 )) && die "need ~80 GB free on internal disk for rebuild, have ${avail} GB"
  local pbf="$SSD/valhalla/data/north-america-latest.osm.pbf"
  echo "downloading (~18 GB, resumable)..."
  resume_download "$GEOFABRIK_URL" "$pbf.new" || die "download failed"
  mv -f "$pbf.new" "$pbf"

  local stage="$AI/valhalla/rebuild"
  local bin="$AI/valhalla/venv-weekly/lib/python3.13/site-packages/valhalla/bin"
  [[ -x "$bin/valhalla_build_tiles" ]] || die "valhalla build binaries not found at $bin"
  rm -rf "$stage"; mkdir -p "$stage/tiles"
  python3 - "$AI/valhalla/valhalla.json" "$stage" <<'PYEOF'
import json, sys
cfg = json.load(open(sys.argv[1])); stage = sys.argv[2]
cfg["mjolnir"]["tile_dir"] = stage + "/tiles"
cfg["mjolnir"]["admin"] = stage + "/admins.sqlite"
json.dump(cfg, open(stage + "/build.json", "w"), indent=2)
PYEOF
  echo "building admins (~15 min)..."
  "$bin/valhalla_build_admins" -c "$stage/build.json" "$pbf" > "$stage/build-admins.log" 2>&1 \
    || die "admin build failed — see $stage/build-admins.log"
  echo "building tiles (~35 min, ALL stages in one run — never resume this)..."
  "$bin/valhalla_build_tiles" -c "$stage/build.json" "$pbf" > "$stage/build-tiles.log" 2>&1 \
    || die "tile build failed — see $stage/build-tiles.log"
  grep -q "Failed to open input file: osmdata_counts.bin" "$stage/build-tiles.log" \
    && die "build shows the osmdata_counts.bin error (silently broken street names) — aborting swap"

  echo "swapping tiles onto SSD..."
  launchctl unload ~/Library/LaunchAgents/local.valhalla.plist 2>/dev/null
  rm -rf "$SSD/valhalla/data/tiles.old"
  mv "$SSD/valhalla/data/tiles" "$SSD/valhalla/data/tiles.old"
  mv "$stage/tiles" "$SSD/valhalla/data/tiles"
  cp -f "$stage/admins.sqlite" "$SSD/valhalla/data/admins.sqlite"
  launchctl load ~/Library/LaunchAgents/local.valhalla.plist

  echo "verifying route (with street names)..."
  local ok=""
  if service_up "http://127.0.0.1:8002/status" 120; then
    ok=$(curl -s --max-time 30 "http://localhost:8002/route" -H 'Content-Type: application/json' \
      -d '{"locations":[{"lat":40.7484,"lon":-73.9857},{"lat":40.7527,"lon":-73.9772}],"costing":"auto"}' \
      | python3 -c "
import json,sys
try:
    t=json.load(sys.stdin)['trip']
    names=any('onto' in m.get('instruction','') for l in t['legs'] for m in l['maneuvers'])
    print('ok' if names else '')
except Exception: print('')")
  fi
  if [[ "$ok" == "ok" ]]; then
    rm -rf "$SSD/valhalla/data/tiles.old" "$stage"
    state_set valhalla "$(geofabrik_date)"
    echo "valhalla OK — new tiles live, street names verified."
    echo "NOTE: the POI database derives from this extract — run 'update poi' next."
  else
    echo "verification failed — ROLLING BACK" >&2
    launchctl unload ~/Library/LaunchAgents/local.valhalla.plist 2>/dev/null
    rm -rf "$SSD/valhalla/data/tiles"
    mv "$SSD/valhalla/data/tiles.old" "$SSD/valhalla/data/tiles"
    launchctl load ~/Library/LaunchAgents/local.valhalla.plist
    die "valhalla update rolled back; old tiles restored. Staging kept at $stage"
  fi
}

# ---------- poi ----------
cmd_update_poi() {
  echo "=== POI: rebuild places database from the current Valhalla OSM extract ==="
  check_ssd
  local pbf="$SSD/valhalla/data/north-america-latest.osm.pbf"
  [[ -f "$pbf" ]] || die "OSM extract not found at $pbf (run 'update valhalla' first)"
  local dir="$AI/poi"
  echo "filtering POI tags (~20 min)..."
  osmium tags-filter "$pbf" nwr/amenity nwr/shop nwr/tourism nwr/leisure \
      nwr/healthcare nwr/emergency nwr/aeroway=aerodrome \
      -o "$dir/pois-filtered.osm.pbf" --overwrite || die "osmium filter failed"
  echo "exporting geometries..."
  osmium export "$dir/pois-filtered.osm.pbf" -f geojsonseq \
      -o "$dir/pois.geojsonl" --overwrite --geometry-types=point,polygon \
      || die "osmium export failed"
  echo "loading SQLite (~5 min)..."
  rm -f "$dir/pois.sqlite.new"
  "$AI/bench/venv/bin/python3" "$dir/poi_load.py" "$dir/pois.geojsonl" "$dir/pois.sqlite.new" \
      || die "POI load failed"
  mv -f "$dir/pois.sqlite.new" "$dir/pois.sqlite"
  cp -f "$dir/pois.sqlite" "$SSD/poi/pois.sqlite"
  rm -f "$dir/pois-filtered.osm.pbf" "$dir/pois.geojsonl"
  state_set poi "$(state_get valhalla)"
  echo "POI database rebuilt ($(du -h "$dir/pois.sqlite" | cut -f1)); backup copied to SSD."
}

# ---------- kiwix ----------
cmd_update_kiwix() {
  echo "=== Kiwix: rescan ZIMs on the SSD ==="
  "$AI/kiwix/refresh-zims.sh"
  echo "(To fetch NEWER wiki versions first: get them from https://library.kiwix.org"
  echo " onto the SSD — see $AI/kiwix/download-zims.sh — then rerun this.)"
}

# ---------- health ----------
health() {
  echo
  echo "=== service health ==="
  local svc code
  for svc in "kiwix:8090/ROOT" "valhalla:8002/status" "photon:2322/api?q=test" "atlas:8095" "tiles:8096/planet/0/0/0.mvt" "terrain:8096/terrain/0/0/0.png"; do
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "http://127.0.0.1:${svc#*:}")
    echo "  ${svc%%:*}: HTTP $code"
  done
}

# ---------- main ----------
mkdir -p "$AI"; touch "$STATE"
case "${1:-menu}" in
  status) cmd_status ;;
  update)
    case "${2:-}" in
      photon)    cmd_update_photon; health ;;
      protomaps) cmd_update_protomaps; health ;;
      valhalla)  cmd_update_valhalla; health ;;
      poi)       cmd_update_poi; health ;;
      kiwix)     cmd_update_kiwix; health ;;
      all)       cmd_update_kiwix; cmd_update_photon; cmd_update_valhalla; cmd_update_poi; cmd_update_protomaps; health ;;
      *) die "usage: pythia-refresh.sh update photon|protomaps|valhalla|poi|kiwix|all" ;;
    esac ;;
  menu)
    cmd_status
    echo
    echo -n "Update which source? [photon/protomaps/valhalla/poi/kiwix/all/none] "
    read choice
    case "$choice" in
      photon|protomaps|valhalla|poi|kiwix|all) "$0" update "$choice" ;;
      *) echo "nothing updated." ;;
    esac ;;
  *) die "usage: pythia-refresh.sh [status|update <source>]" ;;
esac
