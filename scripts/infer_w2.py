#!/usr/bin/env python3
"""W2 → W3: детектор на новом видео → JSON с детекциями (для w3_facts).

Семплит кадры 1 fps (≤145 с = 145 кадров), прогоняет:
  - W2-детектор (7 примитивов) — обязателен, если --weights не пусто
  - COCO rfdetr-base (только person id=0) — опционально, --coco-weights

Пишет 1 или 2 JSON-а: w2_preds/<video>.json (примитивы) и
w2_preds/<video>.persons.json (COCO person). Это вход для w3_facts.

Запуск:
  venv/bin/python scripts/infer_w2.py --video open/videos/Х-15.mov \\
    --weights w2_nano/checkpoint_best_ema.pth \\
    --coco-weights /home/zhus/datathon/coco_base.pth \\
    --out w2_preds/Х-15.json
"""
import argparse
import json
import os
import sys

import cv2

CLASSES = ["banknotes", "money_bag", "document", "safe", "stamp",
           "outerwear", "terminal"]
COCO_PERSON_ID = 1  # COCO категории 1-indexed: person = 1 (не 0!)


def model_shape(model, target: tuple[int, int] | None = None) -> tuple[int, int]:
    """Размер входа, кратный patch_size*num_windows (иначе rfdetr падает).

    Приоритет — resolution из model_config (на нём обучались): W2 -> 384,
    COCO base -> 560. Иначе ближайший кратный блок.
    """
    mc = getattr(model, "model_config", None)
    ps = int(getattr(mc, "patch_size", 16) or 16)
    nw = int(getattr(mc, "num_windows", 4) or 4)
    block = ps * nw
    res = int(getattr(mc, "resolution", 0) or 0)
    if target is None:
        target = (res, res) if res else (576, 576)
    h, w = target
    h2 = max(block, int(round(h / block)) * block)
    w2 = max(block, int(round(w / block)) * block)
    return (h2, w2)



def load_rfdetr(weights: str, num_classes: int | None = None):
    """weights: 'auto' (скачать COCO-веса) или путь к .pth.

    Для .pth берём model_config из чекпоинта и передаём целиком: rfdetr по
    умолчанию собирает другую архитектуру (patch 14/num_windows 4/dec_layers 3),
    и веса грузятся частично (22 слоя остаются случайными). Только полный
    конфиг даёт корректный инференс.
    """
    from rfdetr import RFDETRBase, RFDETRLarge, RFDETRNano, RFDETRSmall

    if weights == "auto":
        return RFDETRBase()  # сам скачает COCO-веса базовой модели

    name = os.path.basename(weights).lower()
    variant = "base"
    for v in ("nano", "small", "base", "large"):
        if v in name:
            variant = v
            break
    cls = {"nano": RFDETRNano, "small": RFDETRSmall,
           "base": RFDETRBase, "large": RFDETRLarge}[variant]

    kwargs: dict = {}
    if weights.endswith(".pth"):
        try:
            import torch
            ck = torch.load(weights, map_location="cpu", weights_only=False)
            mc = ck.get("model_config") if isinstance(ck, dict) else None
            if isinstance(mc, dict):
                kwargs = {k: v for k, v in mc.items()
                          if k not in ("pretrain_weights", "device", "model_name")}
                num_classes = int(kwargs.get("num_classes", num_classes or 7))
        except Exception as e:
            print(f"  ! не прочитать model_config из {weights}: {e}", file=sys.stderr)
        if num_classes is None:
            num_classes = 7  # словарь нашей разметки
        kwargs["num_classes"] = num_classes
    try:
        return cls(pretrain_weights=weights, **kwargs)
    except TypeError:
        return cls(**kwargs)



def predict_frame(model, img, threshold: float, shape: tuple[int, int] | None = None) -> list[dict]:
    dets = model.predict(img, threshold=threshold, shape=shape)
    out = []
    for j in range(len(dets.xyxy)):
        out.append({
            "cls": int(dets.class_id[j]),
            "conf": float(dets.confidence[j]),
            "xyxy": [float(x) for x in dets.xyxy[j]],
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--weights", help="W2 .pth (7 примитивов). Если пусто — только COCO.")
    ap.add_argument("--coco-weights", help="COCO rfdetr (для person)")
    ap.add_argument("--out", help="путь для JSON с примитивами (если есть W2)")
    ap.add_argument("--out-persons", help="путь для JSON с person-детекциями")
    ap.add_argument("--fps", type=float, default=1.0)
    ap.add_argument("--threshold", type=float, default=0.4)
    ap.add_argument("--person-threshold", type=float, default=0.5)
    ap.add_argument("--gpu", default="0")
    args = ap.parse_args()
    if not args.weights and not args.coco_weights:
        ap.error("укажи хотя бы --weights или --coco-weights")

    os.environ.setdefault("CUDA_VISIBLE_DEVICES", args.gpu)

    prim_model = None
    person_model = None
    prim_shape = None
    person_shape = None
    if args.weights:
        prim_model = load_rfdetr(args.weights)
        prim_shape = model_shape(prim_model)
    if args.coco_weights:
        person_model = load_rfdetr(args.coco_weights)  # 80 классов COCO или auto
        person_shape = model_shape(person_model)
    print(f"shape: prims={prim_shape}, person={person_shape}", flush=True)

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f"не открыть {args.video}", file=sys.stderr)
        return 2
    fps_native = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = n_total / fps_native
    step = max(1, int(round(fps_native / args.fps)))
    print(f"видео: {n_total} кадров @ {fps_native:.2f}fps ({duration:.1f}s) → шаг {step}, "
          f"итого ~{int(n_total / step)} инференсов")
    print(f"модели: prims={'W2 '+os.path.basename(args.weights) if args.weights else 'нет'}, "
          f"person={'COCO '+os.path.basename(args.coco_weights) if args.coco_weights else 'нет'}",
          flush=True)

    prim_frames, person_frames = [], []
    idx = 0
    while True:
        ok, img = cap.read()
        if not ok:
            break
        if idx % step == 0:
            t = idx / fps_native
            if prim_model is not None:
                for o in predict_frame(prim_model, img, args.threshold, prim_shape):
                    cls = o["cls"]
                    prim_frames.append({
                        "t": round(t, 3),
                        "cls": CLASSES[cls] if 0 <= cls < len(CLASSES) else f"c{cls}",
                        "conf": o["conf"],
                        "xyxy": o["xyxy"],
                    })
            if person_model is not None:
                for o in predict_frame(person_model, img, args.person_threshold, person_shape):
                    if o["cls"] != COCO_PERSON_ID:
                        continue
                    person_frames.append({
                        "t": round(t, 3),
                        "cls": "person",
                        "conf": o["conf"],
                        "xyxy": o["xyxy"],
                    })
        idx += 1
    cap.release()

    def group_by_t(items: list[dict]) -> list[dict]:
        out: dict[float, list] = {}
        for o in items:
            out.setdefault(o["t"], []).append(
                {"cls": o["cls"], "conf": o["conf"], "xyxy": o["xyxy"]})
        return [{"t": t, "objects": out[t]} for t in sorted(out)]

    meta = {
        "video": os.path.basename(args.video),
        "fps_native": fps_native,
        "fps_infer": args.fps,
        "duration_sec": round(duration, 2),
        "classes": CLASSES,
    }
    if prim_model is not None and args.out:
        out_doc = {**meta, "weights": os.path.basename(args.weights),
                   "threshold": args.threshold, "frames": group_by_t(prim_frames)}
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out_doc, f, ensure_ascii=False, indent=1)
        n = len(out_doc["frames"])
        n_with = sum(1 for fr in out_doc["frames"] if fr["objects"])
        print(f"prims: {n} кадров, {n_with} с детекциями → {args.out}")
    if person_model is not None and args.out_persons:
        out_doc = {**meta, "weights": os.path.basename(args.coco_weights),
                   "threshold": args.person_threshold,
                   "frames": group_by_t(person_frames)}
        os.makedirs(os.path.dirname(args.out_persons) or ".", exist_ok=True)
        with open(args.out_persons, "w", encoding="utf-8") as f:
            json.dump(out_doc, f, ensure_ascii=False, indent=1)
        n = len(out_doc["frames"])
        n_with = sum(1 for fr in out_doc["frames"] if fr["objects"])
        print(f"persons: {n} кадров, {n_with} с person → {args.out_persons}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
