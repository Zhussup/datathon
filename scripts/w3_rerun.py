#!/usr/bin/env python3
"""Перепрогон w3_facts + engine поверх готовых preds (без инференса).

После правки геометрии/правил не нужно пересчитывать детекции:
  venv/bin/python scripts/w3_rerun.py [--preds-dir w2_preds] [--out-dir w3_facts]
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preds-dir", default=str(_ROOT / "w2_preds"))
    ap.add_argument("--out-dir", default=str(_ROOT / "w3_facts"))
    args = ap.parse_args()
    preds = Path(args.preds_dir)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # пары: prim.json + prim.persons.json -> stem
    stems = sorted({p.name[:-5] for p in preds.glob("*.json") if not p.name.endswith(".persons.json")})
    print(f"{len(stems)} видео", flush=True)
    rc = 0
    for i, stem in enumerate(stems, 1):
        prims = preds / f"{stem}.json"
        persons = preds / f"{stem}.persons.json"
        facts = out / f"{stem}.json"
        cmd = [sys.executable, str(_ROOT / "scripts" / "w3_facts.py"),
               "--out", str(facts), "--video", stem]
        if prims.exists():
            cmd += ["--preds", str(prims)]
        if persons.exists():
            cmd += ["--preds-persons", str(persons)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"[{i}] {stem}: w3_facts FAIL\n{r.stderr[-500:]}", flush=True)
            rc = 1
            continue
        v = subprocess.run([sys.executable, str(_ROOT / "scripts" / "run_verdict.py"),
                            "--facts", str(facts), "--out", str(out / f"{stem}.verdict.json")],
                           capture_output=True, text=True)
        line = (v.stdout or "").strip().splitlines()
        print(f"[{i}/{len(stems)}] {stem}: " + (line[0] if line else "verdict?"), flush=True)
        if v.returncode != 0:
            print((v.stderr or "")[-500:], flush=True)
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())