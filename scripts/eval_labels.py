#!/usr/bin/env python3
"""Сверка вердиктов против labels.csv (глобальный критерий 1 ТЗ).

Считает: TP (нарушение+/нарушение+), FP (без+/нарушение+), FN (нарушение+/без+),
TN; для TP — близость таймкодов (окно ±10 c, FAQ 10 допускает сдвиг «по бездействию»).
Дубликаты Х-4=Х-47 и Х-5=Х-48 считаются один раз (по оригиналу).
"""
import argparse
import csv
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
WINDOW = 10.0
DUPS = {"X-47": "Х-4", "Х-48": "Х-5"}   # дубль -> оригинал (учитываем один раз)
LAT = {  # кириллический Х -> латинский X (в labels.csv имена и в preds смешаны)
    ord("Х"): "X", ord("х"): "x",
}


def norm_key(name: str) -> str:
    return name.translate(LAT).lower().replace(".mov", "").strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verdicts", default=str(_ROOT / "w3_facts"))
    ap.add_argument("--labels", default=str(_ROOT / "labels.csv"))
    ap.add_argument("--details", action="store_true", help="печать каждого расхождения")
    args = ap.parse_args()

    labels = {}
    with open(args.labels, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            key = norm_key(r["filename"])
            labels[key] = (r["label"].strip().startswith("нару"),
                           float(r["timestamp_sec"]) if r["timestamp_sec"] else None)

    vdir = Path(args.verdicts)
    tp = fp = fn = tn = 0
    rows = []
    for vf in sorted(vdir.glob("*.verdict.json")):
        key = norm_key(vf.name[:-len(".verdict.json")])
        if key in DUPS:  # дубликаты пропускаем (считается оригинал)
            continue
        lab_is_v, lab_tc = labels.get(key, (None, None))
        if lab_is_v is None:
            continue
        v = json.load(open(vf, encoding="utf-8"))
        is_v = v["verdict"] == "violation"
        tcs = [x["timecode_sec"] for x in v.get("violations", [])]
        if lab_is_v and is_v:
            hit = any(lab_tc is None or abs(t - (lab_tc or 0)) <= WINDOW for t in tcs) if lab_tc else True
            close = (min((abs(t - lab_tc) for t in tcs), default=None) if lab_tc else None)
            rows.append((key, "TP" if hit else "TP-даль", lab_tc, tcs, close))
            tp += 1
        elif lab_is_v and not is_v:
            rows.append((key, "FN ПРОПУСК", lab_tc, tcs, None))
            fn += 1
        elif not lab_is_v and is_v:
            rows.append((key, "FP ЛОЖНЫЙ", None, tcs, None))
            fp += 1
        else:
            rows.append((key, "TN", None, [], None))
            tn += 1

    total = tp + fp + fn + tn
    prec = tp / max(1, tp + fp)
    rec = tp / max(1, tp + fn)
    f1 = 2 * prec * rec / max(prec + rec, 1e-9)
    print(f"итого {total}: TP={tp}  FN={fn} (пропуски!)  FP={fp} (ложные!)  TN={tn}")
    print(f"precision={prec:.2f}  recall={rec:.2f}  F1={f1:.2f}")
    print("Критерий 1 ТЗ: пропуски хуже ложных; злоупотребление no_violation штрафуется.")
    if args.details:
        print("\nвидео  классиф  label@  наши_таймкоды  дельта")
        for r in rows:
            key, cls, ltc, tcs, d = r
            ds = f"{d:.1f}" if d is not None else "-"
            ts = ",".join(f"{t:.0f}" for t in tcs) or "-"
            ls = f"{ltc:.0f}" if ltc is not None else "-"
            print(f"  {key:6} {cls:12} {ls:6}  {ts:14} {ds}")
        return 0
    bad = [r for r in rows if r[1] not in ("TP", "TN")]
    if bad:
        print("\nрасхождения (первые 20):")
        for r in bad[:20]:
            key, cls, ltc, tcs, d = r
            ts = ",".join(f"{t:.0f}" for t in tcs) or "-"
            ls = f"{ltc:.0f}" if ltc is not None else "-"
            print(f"  {key:6} {cls:12} label@{ls}  наши@{ts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())