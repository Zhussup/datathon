#!/usr/bin/env python3
"""Прогон engine на FactTable → verdict.json (формат API раздела 10 ТЗ).

Использование:
  venv/bin/python scripts/run_verdict.py \\
    --facts w3_facts/Х-15.json --out w3_facts/Х-15.verdict.json
"""
import argparse
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from pipeline.facts import FactTable  # noqa: E402
from pipeline.engine import run_engine  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--facts", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    ft = FactTable.from_spec(args.facts)
    r = run_engine(ft)
    out = {
        "video": r["video"],
        "verdict": r["verdict"],
        "violations": r["violations"],
    }
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"  verdict: {r['verdict']} ({len(r['violations'])} events) → {args.out}",
          flush=True)
    for v in r["violations"]:
        print(f"    {v['rule_id']} @ {v['timecode_sec']}s — {v['type']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
