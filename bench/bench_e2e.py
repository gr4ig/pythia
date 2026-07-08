"""End-to-end answer quality and latency: tools ON vs OFF over the question sets.

For each question and mode, runs the agent loop against Ollama with the real
offline tools, grades the answer, and records the full trace.

Usage: bench_e2e.py [--model M] [--set facts|geo|all] [--modes on,off]
                    [--limit N] [outfile.jsonl]
"""
import argparse
import json
import sys
import time
from pathlib import Path

import agent
import grade

QDIR = Path(__file__).parent / "questions"


def load_questions(which):
    files = {"facts": ["facts.jsonl"], "geo": ["geo.jsonl"], "hard": ["hard.jsonl"],
             "all": ["facts.jsonl", "geo.jsonl", "hard.jsonl"]}[which]
    qs = []
    for f in files:
        for line in (QDIR / f).read_text().splitlines():
            if line.strip():
                qs.append(json.loads(line))
    return qs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemma4:26b-mlx")
    ap.add_argument("--set", default="all", choices=["facts", "geo", "hard", "all"])
    ap.add_argument("--modes", default="on,off")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("outfile", nargs="?")
    args = ap.parse_args()

    qs = load_questions(args.set)
    if args.limit:
        qs = qs[: args.limit]
    modes = [m.strip() == "on" for m in args.modes.split(",")]
    out = open(args.outfile, "a") if args.outfile else None

    tally = {}
    for use_tools in modes:
        label = "tools_on" if use_tools else "tools_off"
        correct = 0
        print(f"\n=== {label} ({args.model}, {len(qs)} questions) ===")
        for i, q in enumerate(qs, 1):
            try:
                tr = agent.ask(q["q"], model=args.model, use_tools=use_tools)
            except Exception as e:
                tr = {"answer": f"(harness error: {e})", "total_seconds": 0,
                      "rounds": [], "tool_calls": []}
            ok = grade.grade(tr.get("answer", ""), q["grade"])
            correct += ok
            rec = {
                "bench": "e2e", "mode": label, "model": args.model,
                "id": q["id"], "cat": q["cat"], "question": q["q"],
                "answer": tr.get("answer", ""), "correct": ok,
                "seconds": round(tr.get("total_seconds", 0), 2),
                "llm_rounds": len(tr.get("rounds", [])),
                "tool_calls": [
                    {"name": c["name"], "seconds": c["seconds"]}
                    for c in tr.get("tool_calls", [])
                ],
                "gen_tok_per_s": (tr.get("rounds") or [{}])[-1].get("gen_tok_per_s"),
            }
            mark = "PASS" if ok else "FAIL"
            tools_used = ",".join(c["name"] for c in tr.get("tool_calls", [])) or "-"
            print(f"  [{i:02d}/{len(qs)}] {q['id']} {mark} {rec['seconds']}s "
                  f"tools:[{tools_used}] :: {rec['answer'][:90]!r}")
            if out:
                out.write(json.dumps(rec) + "\n")
                out.flush()
        summary = {"bench": "e2e_summary", "mode": label, "model": args.model,
                   "set": args.set, "n": len(qs), "correct": correct,
                   "accuracy": round(correct / len(qs), 3)}
        tally[label] = summary
        print(f"  -> {correct}/{len(qs)} correct ({summary['accuracy']:.0%})")
        if out:
            out.write(json.dumps(summary) + "\n")
            out.flush()

    print("\n" + json.dumps(tally, indent=1))
    if out:
        out.close()


if __name__ == "__main__":
    main()
