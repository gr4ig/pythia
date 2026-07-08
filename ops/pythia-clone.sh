#!/bin/zsh
# pythia-clone.sh — replicate the entire Pythia system to another volume.
#
#   pythia-clone.sh /Volumes/BackupSSD          full clone (services + data)
#   pythia-clone.sh user@nas:/backups/oracle    over ssh (rsync)
#   pythia-clone.sh <target> --dry-run          show what would copy
#
# What gets cloned:
#   1. ~/.local/ai-services         all service code, configs, venvs, jars
#   2. ~/Library/LaunchAgents/local.*.plist
#   3. Open WebUI data (webui.db: tools, skills, chats) + Ollama models
#   4. The SSD data (ZIMs, valhalla tiles, pmtiles, terrain, photon archive)
#
# Restoring on a new machine: copy 1-3 into place, plug in the cloned SSD
# (or copy 4 onto one, keeping the same volume name), install Homebrew deps
# (openjdk@21, pmtiles, pbzip2, osmium-tool), then launchctl load the plists.
# Full Disk Access + removable-volume prompts must be re-approved there.

set -u
SSD="/Volumes/PYTHIA_SSD"
TARGET="${1:?usage: pythia-clone.sh <target-dir-or-ssh> [--dry-run]}"
shift
RSYNC=(rsync -ah --info=progress2 --delete "$@")

echo "=== Pythia clone -> $TARGET ==="
date

echo "--- 1/4 service directory (~/.local/ai-services) ---"
"${RSYNC[@]}" "$HOME/.local/ai-services/" "$TARGET/ai-services/"

echo "--- 2/4 launchd plists ---"
mkdir -p /tmp/oracle-plists.$$ && cp ~/Library/LaunchAgents/local.*.plist /tmp/oracle-plists.$$/ 2>/dev/null
"${RSYNC[@]}" /tmp/oracle-plists.$$/ "$TARGET/LaunchAgents/"
rm -rf /tmp/oracle-plists.$$

echo "--- 3/4 Open WebUI data + Ollama models ---"
"${RSYNC[@]}" "$HOME/Library/Application Support/open-webui/data/" "$TARGET/open-webui-data/"
"${RSYNC[@]}" "$HOME/.ollama/models/" "$TARGET/ollama-models/"

echo "--- 4/4 SSD data (the big one: ZIMs, maps, tiles) ---"
if [[ -d "$SSD" ]] && ls "$SSD" >/dev/null 2>&1; then
  "${RSYNC[@]}" "$SSD/" "$TARGET/ssd-data/"
else
  echo "SKIPPED: SSD not mounted or not readable from this context." >&2
fi

date
echo "=== clone complete ==="
