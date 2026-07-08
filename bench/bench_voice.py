"""Full voice-pipeline latency: TTS(question) -> STT -> agent+tools -> TTS(answer).

Synthesizes each question with Kokoro, transcribes with Whisper (measuring the
oracle hearing itself), runs the agent, then synthesizes the spoken answer.
Reports per-stage seconds. Uses a subset of questions by default.

Usage: bench_voice.py [--model M] [--limit N] [outfile.jsonl]
"""
import argparse
import io
import json
import time
from pathlib import Path

import requests

import agent
import grade

KOKORO = "https://127.0.0.1:8880"
WHISPER = "https://127.0.0.1:8766"
QDIR = Path(__file__).parent / "questions"


def tts(text):
    t0 = time.time()
    r = requests.post(f"{KOKORO}/v1/audio/speech", verify=False, timeout=300,
                      json={"input": text, "voice": "alloy", "response_format": "wav"})
    r.raise_for_status()
    return r.content, time.time() - t0


def stt(wav_bytes):
    t0 = time.time()
    r = requests.post(f"{WHISPER}/v1/audio/transcriptions", verify=False, timeout=300,
                      files={"file": ("q.wav", io.BytesIO(wav_bytes), "audio/wav")},
                      data={"response_format": "json"})
    r.raise_for_status()
    return r.json().get("text", "").strip(), time.time() - t0


def main():
    import urllib3
    urllib3.disable_warnings()
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemma4:26b-mlx")
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("outfile", nargs="?")
    args = ap.parse_args()

    qs = [json.loads(l) for l in (QDIR / "facts.jsonl").read_text().splitlines() if l.strip()]
    qs += [json.loads(l) for l in (QDIR / "geo.jsonl").read_text().splitlines() if l.strip()]
    qs = qs[:: max(1, len(qs) // args.limit)][: args.limit]

    out = open(args.outfile, "a") if args.outfile else None
    print(f"voice pipeline: {len(qs)} questions, model {args.model}")
    totals = []
    for q in qs:
        wav_q, t_tts_q = tts(q["q"])
        transcript, t_stt = stt(wav_q)
        tr = agent.ask(transcript, model=args.model, use_tools=True)
        answer = tr.get("answer", "")
        wav_a, t_tts_a = tts(answer[:600] if answer else "I do not know.")
        total = t_tts_q + t_stt + tr.get("total_seconds", 0) + t_tts_a
        # end-to-end as the user experiences it: speak -> hear answer start
        ok = grade.grade(answer, q["grade"])
        rec = {
            "bench": "voice", "id": q["id"], "model": args.model,
            "question": q["q"], "transcript": transcript,
            "transcript_exact": transcript.lower().rstrip(".?!") == q["q"].lower().rstrip(".?!"),
            "answer": answer[:300], "correct": ok,
            "tts_question_s": round(t_tts_q, 2), "stt_s": round(t_stt, 2),
            "agent_s": round(tr.get("total_seconds", 0), 2),
            "tts_answer_s": round(t_tts_a, 2), "total_s": round(total, 2),
            "answer_audio_kb": round(len(wav_a) / 1024),
        }
        totals.append(total)
        print(f"  {q['id']} {'PASS' if ok else 'FAIL'} total {rec['total_s']}s "
              f"(tts {rec['tts_question_s']} + stt {rec['stt_s']} + "
              f"agent {rec['agent_s']} + tts {rec['tts_answer_s']})")
        if out:
            out.write(json.dumps(rec) + "\n")
            out.flush()
    if totals:
        summary = {"bench": "voice_summary", "model": args.model, "n": len(totals),
                   "median_total_s": round(sorted(totals)[len(totals) // 2], 2)}
        print(json.dumps(summary))
        if out:
            out.write(json.dumps(summary) + "\n")
            out.close()


if __name__ == "__main__":
    main()
