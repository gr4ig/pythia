#!/bin/zsh
# Launchd entry point: serve every ZIM path listed in zims.list.
# The list is maintained by refresh-zims.sh (run that after adding ZIMs).

LIST="$HOME/.local/ai-services/kiwix/zims.list"
BIN="$HOME/.local/ai-services/kiwix/bin/kiwix-serve"

if [[ ! -s "$LIST" ]]; then
  echo "zims.list is missing or empty; run refresh-zims.sh"
  exit 1
fi

zims=()
while IFS= read -r p; do
  [[ -n "$p" && -e "$p" ]] && zims+=("$p")
done < "$LIST"

if (( ${#zims} == 0 )); then
  echo "No listed ZIM files are readable (SSD not mounted yet?); will retry."
  exit 1
fi

echo "Serving ${#zims} ZIM file(s): ${zims[@]:t}"
exec "$BIN" --port 8090 --address 127.0.0.1 "${zims[@]}"
