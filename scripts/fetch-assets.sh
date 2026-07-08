#!/bin/zsh
# Fetch third-party assets this repo uses but does not redistribute:
#   - MapLibre GL JS + @protomaps/basemaps + maplibre-contour (npm registry)
#   - Protomaps basemap fonts and sprites (GitHub)
#   - JPL DE421 ephemeris for the almanac tool (NASA)
# Run from the repo root. Assets land in services/atlas/web/ and services/almanac/.
set -e
cd "$(dirname "$0")/.."

WEB=services/atlas/web
mkdir -p $WEB/lib $WEB/fonts $WEB/sprites
TMP=$(mktemp -d)

fetch_npm() {  # package version dist-file dest
  curl -sSL "https://registry.npmjs.org/$1/-/${1##*/}-$2.tgz" -o "$TMP/p.tgz"
  tar xzf "$TMP/p.tgz" -C "$TMP" "package/$3"
  cp "$TMP/package/$3" "$4"
  rm -rf "$TMP/package" "$TMP/p.tgz"
}

echo "MapLibre GL JS..."
fetch_npm maplibre-gl 5.24.0 dist/maplibre-gl.js  $WEB/lib/maplibre-gl.js
fetch_npm maplibre-gl 5.24.0 dist/maplibre-gl.css $WEB/lib/maplibre-gl.css
echo "@protomaps/basemaps..."
fetch_npm @protomaps/basemaps 5.7.2 dist/basemaps.js $WEB/lib/basemaps.js
echo "maplibre-contour..."
fetch_npm maplibre-contour 0.1.0 dist/index.min.js $WEB/lib/maplibre-contour.min.js

echo "Protomaps fonts + sprites..."
curl -sSL https://github.com/protomaps/basemaps-assets/archive/refs/heads/main.zip -o "$TMP/assets.zip"
unzip -q -o "$TMP/assets.zip" -d "$TMP"
cp -R "$TMP"/basemaps-assets-main/fonts/*   $WEB/fonts/
cp -R "$TMP"/basemaps-assets-main/sprites/* $WEB/sprites/

echo "JPL DE421 ephemeris (17 MB)..."
curl -sSL https://ssd.jpl.nasa.gov/ftp/eph/planets/bsp/de421.bsp -o services/almanac/de421.bsp

rm -rf "$TMP"
cp services/atlas/index.html $WEB/index.html
echo "done — assets in $WEB and services/almanac/"
