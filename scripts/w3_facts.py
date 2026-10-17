#!/usr/bin/env python3
"""W3 (минимум): JSON детекций (infer_w2.py) → FactTable (для engine.run_engine).

Это НАИВНЫЙ маппер для 1-fps детекций. На тестовом ролике сработает
как первая итерация; точный W3 (с трекингом/размерами/зонами) пишем
после того, как убедимся, что детектор и движок в принципе дают нужный вердикт.

Маппинг:
- banknotes на ≥2 кадрах подряд в зоне «кассир» → event money_handover
- banknotes → safe_door на кадре t → state safe_open
- document на кадре в зоне «кассир» → event doc_check
- terminal на ≥1 кадре → state counter_busy
- stamp на кадре в зоне «кассир» → event data_entry
- safe на всех кадрах → state safe_present (для R3)
- person_enter/visit_end (пороги по плотности banknotes в кадре) → разметка сессий

Сейчас зоны — простые по координатам (треть кадра = зона кассира, низ = сейф).
Это подменяется реальным трекингом в W3.1.

Запуск: venv/bin/python scripts/w3_facts.py --preds w2_preds/Х-23.json \\
        --out fixtures/w3_Х-23.json
"""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict


# Зоны кадра (464x848, ширина x высота): делим на 3 горизонтальные полосы
W, H = 464, 848
CASHIER_Y = (0.30, 0.65)      # где сидит кассир — средняя полоса
SAFE_Y = (0.00, 0.30)         # сейф сверху


def y_of(box):
    cx = (box[1] + box[3]) / 2  # y1+y2 / 2
    return cx / H


def in_zone(box, zone):
    y = y_of(box)
    return zone[0] <= y <= zone[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preds", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    with open(args.preds, encoding="utf-8") as f:
        d = json.load(f)
    frames = d["frames"]
    duration = d.get("duration_sec") or (frames[-1]["t"] if frames else 0)
    classes = d.get("classes", [])

    # Счётчики по кадрам
    by_t = {fr["t"]: Counter(ob["cls"] for ob in fr["objects"]) for fr in frames}

    # ---- события (моменты) ----
    events = defaultdict(list)

    # doc_check: document в зоне кассира
    for fr in frames:
        for ob in fr["objects"]:
            if ob["cls"] == "document" and in_zone(ob["xyxy"], CASHIER_Y):
                events["doc_check"].append(fr["t"])
                break

    # data_entry: stamp в зоне кассира
    for fr in frames:
        for ob in fr["objects"]:
            if ob["cls"] == "stamp" and in_zone(ob["xyxy"], CASHIER_Y):
                events["data_entry"].append(fr["t"])
                break

    # money_handover: banknotes в зоне кассира (на кадре с cash_present эвристикой)
    for fr in frames:
        for ob in fr["objects"]:
            if ob["cls"] == "banknotes" and in_zone(ob["xyxy"], CASHIER_Y):
                events["money_handover"].append(fr["t"])
                break

    # money_to_safe: banknotes в зоне сейфа
    for fr in frames:
        for ob in fr["objects"]:
            if ob["cls"] == "banknotes" and in_zone(ob["xyxy"], SAFE_Y):
                events["money_to_safe"].append(fr["t"])
                break

    # ---- состояния (интервалы) ----
    # safe_present: safe на каждом кадре — у нас статично
    safe_present_frames = [fr["t"] for fr in frames
                            if any(ob["cls"] == "safe" for ob in fr["objects"])]
    safe_intervals = [(safe_present_frames[0], safe_present_frames[-1])] if safe_present_frames else []

    # counter_busy: terminal на кадре
    counter_busy = [fr["t"] for fr in frames
                    if any(ob["cls"] == "terminal" for ob in fr["objects"])]
    counter_busy_intervals = [(counter_busy[0], counter_busy[-1])] if counter_busy else []

    # client_present: banknotes + document в зоне кассира = визит клиента
    # (очень грубо — это первый шаг; в W3.1 заменим трекингом)
    visit_frames = []
    for fr in frames:
        cash = [ob for ob in fr["objects"] if in_zone(ob["xyxy"], CASHIER_Y)]
        if any(ob["cls"] in ("banknotes", "document", "money_bag") for ob in cash):
            visit_frames.append(fr["t"])
    visit_intervals = [(visit_frames[0], visit_frames[-1])] if visit_frames else []

    # safe_open: banknotes в зоне сейфа (как прокси открытого сейфа)
    safe_open_frames = [fr["t"] for fr in frames
                        if any(ob["cls"] in ("banknotes", "money_bag")
                               and in_zone(ob["xyxy"], SAFE_Y) for ob in fr["objects"])]
    safe_open_intervals = [(safe_open_frames[0], safe_open_frames[-1])] if safe_open_frames else []

    # ---- упаковка в FactTable.from_spec ----
    intervals = {
        "client_present": visit_intervals,
        "counter_busy": counter_busy_intervals,
        "safe_present": safe_intervals,
        "safe_open": safe_open_intervals,
    }
    out = {
        "video": d.get("video", "unknown"),
        "duration": duration,
        "tick": 0.5,
        "intervals": {k: [list(iv) for iv in v] for k, v in intervals.items()},
        "events": dict(events),
        "_meta": {
            "source": "w3_facts.py (naive v0)",
            "frames": len(frames),
            "warnings": "no tracking, no person detection, zones are rough",
        },
    }
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"готово: {args.out}")
    print(f"  events: {sum(len(v) for v in events.values())} всего: {dict((k, len(v)) for k, v in events.items())}")
    print(f"  intervals: " + ", ".join(f"{k}={len(v)}" for k, v in intervals.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
