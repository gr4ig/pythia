"""Grading for benchmark answers. Grade specs (in question JSONL):
  {"type": "contains", "value": "1986"}                 substring, case-insensitive
  {"type": "any_of", "values": ["Paris", "France"]}     any substring passes
  {"type": "all_of", "values": ["1969", "Apollo 11"]}   every substring required
  {"type": "number", "value": 8849, "tol": 15}          any number in the answer within tol
"""
import re


def _numbers(text):
    out = []
    for m in re.finditer(r"-?\d[\d,]*\.?\d*", text):
        try:
            out.append(float(m.group(0).replace(",", "")))
        except ValueError:
            pass
    return out


def grade(answer, spec):
    a = (answer or "").lower()
    t = spec["type"]
    if t == "contains":
        return spec["value"].lower() in a
    if t == "any_of":
        return any(v.lower() in a for v in spec["values"])
    if t == "all_of":
        return all(v.lower() in a for v in spec["values"])
    if t == "number":
        tol = spec.get("tol", 0)
        return any(abs(n - spec["value"]) <= tol for n in _numbers(answer or ""))
    raise ValueError(f"unknown grade type {t}")
