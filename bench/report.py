"""Aggregate benchmark JSONL results into a markdown report.

Usage: report.py results/*.jsonl > report.md
"""
import json
import sys
from collections import defaultdict


def main():
    recs = []
    for f in sys.argv[1:]:
        for line in open(f):
            if line.strip():
                recs.append(json.loads(line))

    by = defaultdict(list)
    for r in recs:
        by[r.get("bench")].append(r)

    print("# Pythia benchmark report\n")

    if by.get("retrieval_summary"):
        s = by["retrieval_summary"][-1]
        print("## Retrieval (Kiwix full-text search, all books, USB SSD)\n")
        print(f"- {s['n_queries']} queries")
        print(f"- cold: median {s['cold_median_s']} s, p90 {s['cold_p90_s']} s")
        print(f"- warm: median {s['warm_median_s']} s, p90 {s['warm_p90_s']} s\n")

    if by.get("article_fetch"):
        xs = [r["seconds"] for r in by["article_fetch"]]
        print(f"- article fetch: median {sorted(xs)[len(xs)//2]} s over {len(xs)} articles\n")

    if by.get("tokens"):
        print("## Model throughput (Ollama)\n")
        print("| model | load s | prompt tok/s | gen tok/s |")
        print("|---|---|---|---|")
        seen = {}
        for r in by["tokens"]:
            seen[r["model"]] = r
        for m, r in sorted(seen.items()):
            print(f"| {m} | {r['load_s']} | {r['prompt_tok_per_s']} | {r['gen_tok_per_s']} |")
        print()

    if by.get("e2e_summary"):
        print("## Answer quality: offline tools ON vs OFF\n")
        print("| model | set | mode | accuracy |")
        print("|---|---|---|---|")
        for s in by["e2e_summary"]:
            print(f"| {s['model']} | {s['set']} | {s['mode']} | {s['correct']}/{s['n']} ({s['accuracy']:.0%}) |")
        print()

    if by.get("e2e"):
        print("### Latency (e2e, seconds per answered question)\n")
        agg = defaultdict(list)
        for r in by["e2e"]:
            agg[(r["model"], r["mode"])].append(r["seconds"])
        print("| model | mode | median s | p90 s | max s |")
        print("|---|---|---|---|---|")
        for (m, mode), xs in sorted(agg.items()):
            xs = sorted(xs)
            print(f"| {m} | {mode} | {xs[len(xs)//2]} | "
                  f"{xs[min(len(xs)-1, int(0.9*(len(xs)-1)))]} | {xs[-1]} |")
        print()
        wrong = [r for r in by["e2e"] if not r["correct"]]
        if wrong:
            print("### Failures\n")
            for r in wrong:
                print(f"- `{r['id']}` [{r['mode']}] {r['question']}  \n"
                      f"  answered: {r['answer'][:140]!r}")
            print()

    if by.get("voice"):
        print("## Voice pipeline (speak question -> hear answer)\n")
        print("| id | correct | TTS-q | STT | agent | TTS-a | total s |")
        print("|---|---|---|---|---|---|---|")
        for r in by["voice"]:
            print(f"| {r['id']} | {'yes' if r['correct'] else 'no'} | "
                  f"{r['tts_question_s']} | {r['stt_s']} | {r['agent_s']} | "
                  f"{r['tts_answer_s']} | {r['total_s']} |")
        if by.get("voice_summary"):
            s = by["voice_summary"][-1]
            print(f"\nmedian end-to-end: **{s['median_total_s']} s** over {s['n']} questions\n")


if __name__ == "__main__":
    main()
