#!/bin/zsh
# Rescan the SSD for ZIM files and restart kiwix-serve with all of them.
# Run this from Terminal after adding/removing ZIM files:
#   ~/.local/ai-services/kiwix/refresh-zims.sh
#
# (It must run from an interactive app like Terminal because macOS privacy
# controls block background services from listing removable-volume folders.
# If macOS asks to allow access to files on a removable volume, click Allow.)

ZIM_DIR="/Volumes/PYTHIA_SSD"
LIST="$HOME/.local/ai-services/kiwix/zims.list"

if [[ ! -d "$ZIM_DIR" ]]; then
  echo "SSD not mounted at $ZIM_DIR" >&2
  exit 1
fi

if ! ls "$ZIM_DIR" >/dev/null 2>&1; then
  echo "macOS denied access to $ZIM_DIR." >&2
  echo "Grant this app access under System Settings > Privacy & Security > Files and Folders (or Full Disk Access) and rerun." >&2
  exit 1
fi

# Gather ZIMs from all known locations. If the same filename exists in more
# than one place, the first location listed wins: SSD zims/ folder, then SSD
# root, then the internal staging dir (downloads not yet moved to the SSD).
STAGE="$HOME/.local/ai-services/kiwix/zims"
zims=()
typeset -A seen
for z in "$ZIM_DIR/zims"/*.zim(N) "$ZIM_DIR"/*.zim(N) "$STAGE"/*.zim(N); do
  [[ -n "${seen[${z:t}]}" ]] && continue
  seen[${z:t}]=1
  zims+=("$z")
done

if (( ${#zims} == 0 )); then
  echo "No .zim files found in $ZIM_DIR, $ZIM_DIR/zims, or $STAGE" >&2
  exit 1
fi

print -l "${zims[@]}" > "$LIST"
launchctl kickstart -k "gui/$(id -u)/local.kiwix-serve"
sleep 2
echo "kiwix-serve restarted with ${#zims} ZIM file(s):"
print -l "  ${zims[@]:t}"
echo "Check http://127.0.0.1:8090 to browse them."
