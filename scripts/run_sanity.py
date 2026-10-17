#!/usr/bin/env python3
"""Смоук-тест движка на рукописных таблицах фактов (fixtures/*.json).

Мера правильности архитектуры: на всех 6 фикстурах движок даёт ожидаемый
вердикт, набор правил и таймкоды. Перцепция позже обязана лишь воспроизвести
этот словарь фактов из видео.
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.facts import FactTable   # noqa: E402
from pipeline.engine import run_engine  # noqa: E402


def main() -> int:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fixtures = sorted(glob.glob(os.path.join(root, "fixtures", "*.json")))
    fails = 0
    for path in fixtures:
        with open(path, encoding="utf-8") as f:
            spec = json.load(f)
        res = run_engine(FactTable.from_spec(path))
        exp = spec.get("expect", {})
        exp_v = exp.get("verdict", "no_violation")
        exp_ids = sorted(exp.get("rule_ids", []))
        exp_ts = exp.get("rule_timecodes", {})
        got_ids = sorted({v["rule_id"] for v in res["violations"]})
        got = {v["rule_id"]: v["timecode_sec"] for v in res["violations"]}
        ok = res["verdict"] == exp_v and got_ids == exp_ids
        if ok:
            for rid, want in exp_ts.items():
                if rid in got and abs(got[rid] - want) > 1.5:
                    ok = False
        fails += 0 if ok else 1
        expd = f'{exp_v}: {", ".join(exp_ids) or "-"}'
        gotd = f'{res["verdict"]}: {", ".join(got_ids) or "-"}'
        print(f'{spec["video"]:<5} {expd:<38} {gotd:<38} {"OK" if ok else "FAIL"}')
        for v in res["violations"]:
            mark = f' [признак]' if not v["confident"] else f' [{v["npa"]}]'
            print(f'      - {v["rule_id"]} @{v["timecode_sec"]}s  {v["type"]}{mark}')
        if not ok:
            print("      !! подробности:")
            print(json.dumps(res["violations"], ensure_ascii=False, indent=8))
    print()
    print("ПРОВАЛ" if fails else "ВСЕ ОК", f"({len(fixtures)} фикстур)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())