#!/usr/bin/env python3
"""W3 v1: детекции (W2 + COCO person) → FactTable (для pipeline.engine).

Вход — JSON от infer_w2.py (с persons), либо 2 файла: --preds (примитивы)
и --preds-persons (COCO). На 0.5 c сетке (TICK из facts.py) вычисляет
состояния-маски и события-моменты, которые ждёт движок (rules.py).

Словарь состояний (см. rules.py):
  client_present, cashier_present, cashier_away, banknotes_on_desk,
  money_bag_on_desk, outerwear_on_desk, safe_open, safe_present,
  clients_2plus, stamp_on_desk, screen_open.
  Не выдаёмся без детектора: door_open, key_in_lock, bag_on_desk.

События:
  doc_check, money_handover, money_to_safe, data_entry, count_start,
  walk_away, person_enter.

Запуск:
  venv/bin/python scripts/w3_facts.py \\
    --preds w2_preds/Х-15.json \\
    --preds-persons w2_preds/Х-15.persons.json \\
    --out fixtures/w3_Х-15.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict

# чтобы работал и как `python scripts/w3_facts.py`, и как `python -m`
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from pipeline.facts import TICK, SESSION_BRIDGE_GAP, SESSION_MIN_DUR

# Зоны кадра (464x848, ширина x высота). Делим по Y, 0 — верх.
# Ракурс ТЗ: камера сверху, стол в центре (0.45–0.85), сейф справа (0.35–0.55),
# человек ЗА столом попадает в полосу 0.2–0.7 (y = глубина, не роль!).
W, H = 464, 848
CASHIER_Y = (0.30, 0.65)      # рабочий стол (примитивы на нём)
SAFE_Y = (0.00, 0.30)         # сейф — уточнить по кадрам; пока верх
COUNTER_Y = (0.55, 0.80)      # legacy
# Ракурс ТЗ: y = ГЛУБИНА. По кадрам Х-15: клиент у стойки cy≈0.47,
# кассир за столом cy≈0.69. Клиент — верхняя полоса, кассир — нижняя.
CLIENT_BAND = (0.20, 0.58)    # клиент у стойки (со стороны посетителей)
CASHIER_BAND = (0.15, 0.85)   # кассовая зона целиком (кто-то рядом со столом)
DESK_BAND = CASHIER_BAND      # «у стола есть человек» = кассир на месте

# W2-примитивы
PRIM_BANKNOTES = "banknotes"
PRIM_MONEY_BAG = "money_bag"
PRIM_DOCUMENT = "document"
PRIM_SAFE = "safe"
PRIM_STAMP = "stamp"
PRIM_OUTERWEAR = "outerwear"
PRIM_TERMINAL = "terminal"

# COCO
PERSON = "person"


def cy(box, h: int = H) -> float:
    return (box[1] + box[3]) / 2 / h


def in_zone(box, zone) -> bool:
    return zone[0] <= cy(box) <= zone[1]


def crosses_desk(person_box: tuple, term_boxes: list, frac: float = 0.25) -> bool:
    """Человек «у рабочего места»: его bbox по x перекрывает bbox терминала
    (терминал стоит на столе). Порог — доля ширины человека (отошедший в
    сторону кассир теряет пересечение, стоящий за столом сохраняет)."""
    wp = max(1.0, person_box[2] - person_box[0])
    for tb in term_boxes:
        inter = min(person_box[2], tb[2]) - max(person_box[0], tb[0])
        if max(0.0, inter) / wp >= frac:
            return True
    return False


def load_preds(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def merge_frames(prims: dict | None, persons: dict | None) -> list[dict]:
    """Сливает два JSON-а (примитивы + person) в общий список кадров.

    Кадр = {"t": float, "prims": [...], "persons": [...]}.
    """
    times: dict[float, dict] = {}
    if prims:
        for fr in prims.get("frames", []):
            slot = times.setdefault(fr["t"], {"t": fr["t"], "prims": [], "persons": []})
            slot["prims"] = fr.get("objects", [])
    if persons:
        for fr in persons.get("frames", []):
            slot = times.setdefault(fr["t"], {"t": fr["t"], "prims": [], "persons": []})
            slot["persons"] = fr.get("objects", [])
    return [times[t] for t in sorted(times)]


def has(objs: list[dict], cls: str) -> bool:
    return any(o["cls"] == cls for o in objs)


def first_in_zone(objs: list[dict], cls: str, zone: tuple[float, float]) -> dict | None:
    for o in objs:
        if o["cls"] == cls and in_zone(o["xyxy"], zone):
            return o
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preds", help="JSON с примитивами (7 классов W2)")
    ap.add_argument("--preds-persons", help="JSON с COCO-person (id 0)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--video", default="unknown")
    args = ap.parse_args()
    if not args.preds and not args.preds_persons:
        ap.error("укажи --preds и/или --preds-persons")

    prims = load_preds(args.preds) if args.preds else None
    persons = load_preds(args.preds_persons) if args.preds_persons else None
    frames = merge_frames(prims, persons)
    if not frames:
        # нет детекций вообще — отдаём пустые маски (1 тик @ 0.0),
        # engine выдаст no_violation; perception остаётся «обработано, не найдено»
        video_name = (prims or persons or {}).get("video", args.video)
        duration = (prims or persons or {}).get("duration_sec") or 0.0
        tick = TICK
        n = max(1, int(round(duration / tick)) + 1) if duration else 1
        empty = {
            "video": video_name, "duration": duration, "tick": tick,
            "intervals": {k: [] for k in (
                "client_present", "cashier_present", "cashier_away",
                "banknotes_on_desk", "money_bag_on_desk", "outerwear_on_desk",
                "safe_open", "safe_present", "clients_2plus",
                "stamp_on_desk", "screen_open",
            )},
            "events": {},
            "_meta": {"source": "w3_facts.py v1 (EMPTY — detector found nothing)",
                      "frames": 0, "n_ticks": n, "n_tracks": 0,
                      "prims_source": args.preds, "persons_source": args.preds_persons,
                      "warnings": "no detections from any detector"},
        }
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(empty, f, ensure_ascii=False, indent=1)
        print(f"готово (ПУСТО): {args.out}")
        print("  детектор ничего не нашёл — engine выдаст no_violation")
        return 0

    duration = (prims or persons or {}).get("duration_sec") or frames[-1]["t"]
    tick = TICK
    n = int(round(duration / tick)) + 1

    # Списки per-tick
    prim_by_t = {fr["t"]: fr["prims"] for fr in frames}
    person_by_t = {fr["t"]: fr["persons"] for fr in frames}
    times = [fr["t"] for fr in frames]

    # ---------- трекинг людей (IoU) ----------
    # Импортим локально, чтобы скрипт работал и без него
    from w3_track import track
    person_dets = {t: [tuple(o["xyxy"]) for o in person_by_t.get(t, [])] for t in times}
    tracks = track(person_dets, iou_threshold=0.3, max_gap=2)

    # track_id -> [(t, xyxy, cy)]
    track_history: dict[int, list[tuple[float, tuple, float]]] = {}
    for tid, samples in tracks.items():
        for t, box in samples:
            track_history.setdefault(tid, []).append((t, box, cy(box)))

    # ---------- состояния: сначала ПОКАДРОВО, потом заливка на тиковую сетку ----------
    # Кадры идут с периодом dt (обычно 1 c), а тики — 0.5 c. Нельзя вычислять
    # состояния на тиках напрямую: тики без кадра («нет данных») ловушкой идут
    # как «человека нет». Поэтому все маски считаются per-frame, затем каждый
    # тик наследует значение кадра-владельца (тик целиком лежит в интервале
    # [t_k, t_{k+1}) своего кадра).
    fkeys = ("client_present", "cashier_present", "clients_2plus",
             "banknotes_on_desk", "money_bag_on_desk", "outerwear_on_desk",
             "safe_open", "safe_present", "stamp_on_desk", "screen_open")
    fvals: dict[str, list[bool]] = {k: [False] * len(times) for k in fkeys}

    for k, t in enumerate(times):
        prims_t = prim_by_t.get(t, [])
        persons_t = person_by_t.get(t, [])
        # y = ГЛУБИНА: клиент — верхняя полоса (у стойки со стороны посетителей).
        # «У рабочего места» = bbox по x перекрывает терминал на столе (маркер
        # стола, детектится на каждом кадре): y-полоса не отличает отошедшего
        # В СТОРОНУ кассира — он остаётся в той же полосе глубины (Х-11/Х-24:
        # кассир ушла к дверям, штамп/экран остались на столе).
        at_client = [p for p in persons_t if in_zone(p["xyxy"], CLIENT_BAND)]
        term_boxes = [o["xyxy"] for o in prims_t if o["cls"] == PRIM_TERMINAL]
        if term_boxes:
            at_desk = [p for p in persons_t if crosses_desk(p["xyxy"], term_boxes)]
        else:
            at_desk = [p for p in persons_t if in_zone(p["xyxy"], CASHIER_BAND)]
        if at_client:
            fvals["client_present"][k] = True
        if at_desk:
            fvals["cashier_present"][k] = True
        if len(at_client) >= 2:
            fvals["clients_2plus"][k] = True
        # примитивы на рабочем столе
        for prim, key in ((PRIM_BANKNOTES, "banknotes_on_desk"),
                          (PRIM_MONEY_BAG, "money_bag_on_desk"),
                          (PRIM_OUTERWEAR, "outerwear_on_desk"),
                          (PRIM_STAMP, "stamp_on_desk")):
            if any(o["cls"] == prim and in_zone(o["xyxy"], CASHIER_Y) for o in prims_t):
                fvals[key][k] = True
        if any(o["cls"] == PRIM_SAFE for o in prims_t):
            fvals["safe_present"][k] = True
        # safe_open: банкноты/мешок в зоне сейфа
        if any(o["cls"] in (PRIM_BANKNOTES, PRIM_MONEY_BAG) and in_zone(o["xyxy"], SAFE_Y)
               for o in prims_t):
            fvals["safe_open"][k] = True
        if any(o["cls"] == PRIM_TERMINAL for o in prims_t):
            fvals["screen_open"][k] = True

    # cashier_away (покадрово): после первого «кого-то видели» GAP_FRAMES
    # подряд ни одного человека в кассовой зоне → «отошёл».
    # GAP_FRAMES=2: одиночный пропущенный кадр детекции не считается уходом.
    GAP_FRAMES = 2
    kp = fvals["cashier_present"]
    ca_f = [False] * len(times)
    ever_seen = False
    gap = 0
    for k, v in enumerate(kp):
        if v:
            ever_seen = True
            gap = 0
            continue
        if not ever_seen:
            continue
        gap += 1
        ca_f[k] = gap >= GAP_FRAMES
    fvals["cashier_away"] = ca_f

    # заливка тиков: тик i ∈ [0.5c*i, 0.5c*(i+1)) принадлежит кадру t_k,
    # на чей интервал попадает центр тика
    states: dict[str, list[bool]] = {}
    for key, vals in fvals.items():
        row = [False] * n
        j = 0
        for i in range(n):
            c = (i + 0.5) * tick
            while j + 1 < len(times) and c >= times[j + 1]:
                j += 1
            if c >= times[j]:
                row[i] = vals[j]
        states[key] = row

    # ---------- события ----------
    events: dict[str, list[float]] = defaultdict(list)

    def tick_idx(t: float) -> int:
        return max(0, min(n - 1, int(round(t / tick + 1e-9))))

    # doc_check
    for t in times:
        if any(o["cls"] == PRIM_DOCUMENT and in_zone(o["xyxy"], CASHIER_Y)
               for o in prim_by_t.get(t, [])):
            events["doc_check"].append(t)
            break
    # data_entry
    for t in times:
        if any(o["cls"] == PRIM_STAMP and in_zone(o["xyxy"], CASHIER_Y)
               for o in prim_by_t.get(t, [])):
            events["data_entry"].append(t)
            break

    # money_handover: banknotes ПОЯВИЛСЯ в зоне кассира (а в предыдущем 5 c не было).
    # Первые 2 c ролика пропускаем: на открывающем кадре деньги уже на столе —
    # это не «передача», о произошедшем до записи ничего утверждать нельзя.
    HANDOVER_LOOK = 5.0
    for i, t in enumerate(times):
        if t < 2.0:
            continue
        if not any(o["cls"] == PRIM_BANKNOTES and in_zone(o["xyxy"], CASHIER_Y)
                   for o in prim_by_t.get(t, [])):
            continue
        # за последние HANDOVER_LOOK секунд не было banknotes
        prev = [tp for tp in times[:i] if t - tp <= HANDOVER_LOOK]
        if any(any(o["cls"] == PRIM_BANKNOTES and in_zone(o["xyxy"], CASHIER_Y)
                   for o in prim_by_t.get(tp, [])) for tp in prev):
            continue
        events["money_handover"].append(t)

    # money_to_safe: banknotes/money_bag ПОЯВИЛСЯ в зоне сейфа (в SAFE_Y)
    for i, t in enumerate(times):
        if not any(o["cls"] in (PRIM_BANKNOTES, PRIM_MONEY_BAG) and in_zone(o["xyxy"], SAFE_Y)
                   for o in prim_by_t.get(t, [])):
            continue
        prev = [tp for tp in times[:i] if t - tp <= HANDOVER_LOOK]
        if any(any(o["cls"] in (PRIM_BANKNOTES, PRIM_MONEY_BAG) and in_zone(o["xyxy"], SAFE_Y)
                   for o in prim_by_t.get(tp, [])) for tp in prev):
            continue
        events["money_to_safe"].append(t)

    # count_start: banknotes на столе + клиент в кадре + не было money_handover в последние 5 c
    cp_mask = states["client_present"]
    for i, t in enumerate(times):
        if not states["banknotes_on_desk"][tick_idx(t)]:
            continue
        if not cp_mask[tick_idx(t)]:
            continue
        # в последние 5 c не было money_handover
        if any(t - h <= HANDOVER_LOOK for h in events["money_handover"]):
            continue
        # и не было count_start в последние 3 c (де-дупликация)
        if any(t - c <= 3.0 for c in events["count_start"]):
            continue
        events["count_start"].append(t)

    # walk_away: cashier_present был, пропал на ≥3 тика, при этом в кадре есть ценности
    # (грубо: cashier_away уже сглажен выше)
    for t in times:
        i = tick_idx(t)
        if not states["cashier_away"][i]:
            continue
        if not (states["banknotes_on_desk"][i] or states["money_bag_on_desk"][i] or
                states["safe_open"][i]):
            continue
        # де-дупликация: один walk_away на эпизод
        if events["walk_away"] and t - events["walk_away"][-1] < 5.0:
            continue
        events["walk_away"].append(t)

    # person_enter: новый track_id появился (когда до этого было 0 tracks в кадре)
    seen_tids: set[int] = set()
    for tid, samples in tracks.items():
        first_t = samples[0][0]
        if not seen_tids and False:  # первый вообще — не считается (это кассир)
            seen_tids.add(tid)
            continue
        if tid in seen_tids:
            continue
        # новый: но в первые 2 секунды ролика не считаем (часто это кадр открытия)
        if first_t < 2.0:
            seen_tids.add(tid)
            continue
        # только если в этот момент идёт клиентская зона (не кассир с самого начала)
        # Упрощение: считаем все новые треки после 2 с
        events["person_enter"].append(first_t)
        seen_tids.add(tid)

    # ---------- интервалы для FactTable ----------
    def mask_to_intervals(mask: list[bool]) -> list[tuple[float, float]]:
        runs: list[tuple[float, float]] = []
        start: float | None = None
        for i, v in enumerate(mask):
            t0 = i * tick
            t1 = t0 + tick
            if v:
                if start is None:
                    start = t0
                end = t1
            elif start is not None:
                runs.append((start, end))
                start = None
        if start is not None:
            runs.append((start, end))
        return runs

    # Сессии из client_present (со сглаживанием SESSION_BRIDGE_GAP)
    cp_intervals_raw = mask_to_intervals(states["client_present"])
    merged: list[list[float]] = []
    for a, b in cp_intervals_raw:
        if merged and a - merged[-1][1] <= SESSION_BRIDGE_GAP:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    sessions_intervals = [(a, b) for a, b in merged if b - a >= SESSION_MIN_DUR]

    intervals_out: dict[str, list[list[float]]] = {}
    for k, mask in states.items():
        intervals_out[k] = [list(iv) for iv in mask_to_intervals(mask)]

    out = {
        "video": (prims or persons or {}).get("video", args.video),
        "duration": duration,
        "tick": tick,
        "intervals": intervals_out,
        "events": dict(events),
        "_meta": {
            "source": "w3_facts.py v1 (zones + IoU track)",
            "frames": len(frames),
            "n_ticks": n,
            "n_tracks": len(tracks),
            "prims_source": args.preds,
            "persons_source": args.preds_persons,
            "warnings": "no door_open, no key_in_lock, no bag_on_desk, no drink (no detector)",
        },
    }
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"готово: {args.out}")
    print(f"  duration={duration:.1f}s  ticks={n}  tracks={len(tracks)}")
    print(f"  events: " + ", ".join(f"{k}={len(v)}" for k, v in events.items()))
    print(f"  intervals: " + ", ".join(f"{k}={len(v)}" for k, v in intervals_out.items()))
    print(f"  sessions (client_present merged): {len(sessions_intervals)}")
    return 0


if __name__ == "__main__":
    __import__("sys").exit(main())
