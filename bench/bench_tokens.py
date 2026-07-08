"""Tokens/sec for each local Ollama model: prompt processing and generation.

Usage: bench_tokens.py [outfile.jsonl] [model ...]
"""
import json
import sys
import time

import requests

OLLAMA = "http://127.0.0.1:11434"
PROMPT = (
    "Explain in about 200 words how a lead-acid battery works, including the "
    "chemistry of charge and discharge and why cold weather reduces capacity."
)


def local_models():
    r = requests.get(f"{OLLAMA}/api/tags", timeout=15)
    return [m["name"] for m in r.json().get("models", [])
            if m.get("size") and "cloud" not in m["name"]]


def bench(model):
    t0 = time.time()
    r = requests.post(f"{OLLAMA}/api/generate", json={
        "model": model, "prompt": PROMPT, "stream": False,
        "options": {"temperature": 0, "num_predict": 400},
    }, timeout=900)
    r.raise_for_status()
    d = r.json()
    wall = time.time() - t0
    pe, pd = d.get("prompt_eval_count", 0), d.get("prompt_eval_duration", 1)
    ge, gd = d.get("eval_count", 0), d.get("eval_duration", 1)
    return {
        "bench": "tokens", "model": model,
        "load_s": round(d.get("load_duration", 0) / 1e9, 2),
        "prompt_tokens": pe, "prompt_tok_per_s": round(pe / (pd / 1e9), 1),
        "gen_tokens": ge, "gen_tok_per_s": round(ge / (gd / 1e9), 1),
        "wall_s": round(wall, 2),
    }


def main():
    args = sys.argv[1:]
    out = open(args.pop(0), "a") if args and args[0].endswith(".jsonl") else None
    models = args or local_models()
    for m in models:
        print(f"benchmarking {m} (includes model load on first call)...")
        try:
            rec = bench(m)
        except Exception as e:
            print(f"  SKIP {m}: {e}")
            continue
        print(" ", json.dumps(rec))
        if out:
            out.write(json.dumps(rec) + "\n")
    if out:
        out.close()


if __name__ == "__main__":
    main()
