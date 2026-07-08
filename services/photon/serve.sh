#!/bin/zsh
# Photon offline geocoder (planet) — port 2322
# Live OpenSearch index on internal NVMe: USB-SSD fsync latency (10-16 s per
# cluster-state write) made startup time out and would stall the node at
# runtime. The compressed archive stays on the SSD for re-extraction.
BASE="$HOME/.local/ai-services/photon"
DATA="$HOME/.local/ai-services/photon"
JAVA="/opt/homebrew/opt/openjdk@21/bin/java"
exec "$JAVA" -Xmx4g -jar "$BASE/photon-1.2.1.jar" serve \
    -data-dir "$DATA" \
    -listen-ip 127.0.0.1 \
    -listen-port 2322 \
    -cors-any \
    -j 4
