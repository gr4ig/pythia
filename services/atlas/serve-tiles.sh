#!/bin/zsh
# go-pmtiles tile server — port 8096
# Serves every .pmtiles archive in the SSD protomaps dir as /<name>/{z}/{x}/{y}.mvt
exec /opt/homebrew/bin/pmtiles serve "/Volumes/PYTHIA_SSD/protomaps" \
    --port 8096 --cors "*"
