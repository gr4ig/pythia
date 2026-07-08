"""Minimal agent loop against Ollama /api/chat with the real oracle tools.

Returns the final answer plus a full trace: per-round LLM timings and token
counts, every tool call with arguments and duration.
"""
import json
import time

import requests

import tools_bridge

OLLAMA = "http://127.0.0.1:11434"

SYSTEM_TOOLS = (
    "You are an offline oracle running on a laptop with no internet access. "
    "Answer using the provided offline tools: search the wiki library for facts, "
    "geocode place names to coordinates, route between coordinates (North America "
    "only), and look up elevations. Chain tools as needed (e.g. geocode two places, "
    "then route between their coordinates). Answer concisely and include the key "
    "number or fact requested."
)
SYSTEM_BARE = (
    "You are an offline oracle running on a laptop with no internet access. "
    "Answer from your own knowledge. Answer concisely and include the key "
    "number or fact requested."
)


def ask(question, model="gemma4:26b-mlx", use_tools=True, max_rounds=8, timeout=600):
    messages = [
        {"role": "system", "content": SYSTEM_TOOLS if use_tools else SYSTEM_BARE},
        {"role": "user", "content": question},
    ]
    tools = tools_bridge.ollama_tools() if use_tools else None
    trace = {"model": model, "use_tools": use_tools, "rounds": [], "tool_calls": []}
    t_start = time.time()

    seen_calls = set()
    for rnd in range(max_rounds):
        last = rnd == max_rounds - 1
        body = {"model": model, "messages": messages, "stream": False,
                "options": {"temperature": 0}}
        if tools and not last:
            body["tools"] = tools
        elif tools and last:
            messages.append({
                "role": "user",
                "content": "Stop using tools. Give your final answer now based "
                           "on the information you have gathered."})
        t0 = time.time()
        r = requests.post(f"{OLLAMA}/api/chat", json=body, timeout=timeout)
        r.raise_for_status()
        d = r.json()
        msg = d.get("message", {})
        trace["rounds"].append({
            "seconds": time.time() - t0,
            "prompt_tokens": d.get("prompt_eval_count"),
            "gen_tokens": d.get("eval_count"),
            "gen_tok_per_s": round(d.get("eval_count", 0) / (d.get("eval_duration", 1) / 1e9), 1)
            if d.get("eval_duration") else None,
        })
        calls = msg.get("tool_calls") or []
        if not calls:
            trace["answer"] = (msg.get("content") or "").strip()
            trace["total_seconds"] = time.time() - t_start
            return trace
        messages.append(msg)
        for call in calls:
            fn = call.get("function", {})
            name = fn.get("name", "")
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            sig = name + json.dumps(args, sort_keys=True)
            if sig in seen_calls:
                out, dt = ("You already made this exact tool call and have its "
                           "result above. Answer the question now with the "
                           "information you have."), 0.0
            else:
                seen_calls.add(sig)
                out, dt = tools_bridge.execute(name, args)
            trace["tool_calls"].append(
                {"name": name, "args": args, "seconds": round(dt, 3),
                 "result_chars": len(out)})
            messages.append({"role": "tool", "tool_name": name, "content": out[:16000]})

    trace["answer"] = "(agent hit max tool rounds without a final answer)"
    trace["total_seconds"] = time.time() - t_start
    return trace


if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "How far is it by car from the Empire State Building to Yankee Stadium?"
    tr = ask(q)
    print(json.dumps(tr, indent=1))
