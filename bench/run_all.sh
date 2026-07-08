#!/bin/zsh
# Run the full Oracle benchmark suite. Results land in results/<timestamp>/.
# Takes a couple of hours (dominated by the tools-on/off e2e pass).
set -e
BENCH="$HOME/.local/ai-services/bench"
PY="$BENCH/venv/bin/python3"
TS=$(date +%Y%m%d-%H%M)
OUT="$BENCH/results/$TS"
mkdir -p "$OUT"
cd "$BENCH"

echo "### 1/4 retrieval latency"
"$PY" bench_retrieval.py "$OUT/retrieval.jsonl"

echo "### 2/4 model throughput"
"$PY" bench_tokens.py "$OUT/tokens.jsonl"

echo "### 3/4 end-to-end quality + latency (tools on/off)"
"$PY" bench_e2e.py --set all --modes on,off "$OUT/e2e.jsonl"

echo "### 4/4 voice pipeline"
"$PY" bench_voice.py --limit 8 "$OUT/voice.jsonl"

"$PY" report.py "$OUT"/*.jsonl > "$OUT/report.md"
echo
echo "report: $OUT/report.md"
