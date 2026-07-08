#!/bin/zsh
# Valhalla offline routing service (North America) — port 8002
# Tiles + config live in this directory; see valhalla.json for paths.
BASE="$HOME/.local/ai-services/valhalla"
exec "$BASE/venv/lib/python3.13/site-packages/valhalla/bin/valhalla_service" "$BASE/valhalla.json" 2
