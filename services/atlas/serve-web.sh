#!/bin/zsh
# Oracle Atlas static page (MapLibre + local fonts/sprites) — port 8095
BASE="$HOME/.local/ai-services/atlas/web"
exec /usr/bin/python3 -m http.server 8095 --bind 127.0.0.1 --directory "$BASE"
