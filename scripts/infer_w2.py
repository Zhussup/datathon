#!/usr/bin/env python3
"""W2 → W3: детектор на новом видео → JSON с детекциями на каждом кадре (для facts.py).

Семплит кадры 1 fps (≤145 с = 145 кадров), прогоняет RF-DETR, пишет JSON
{wideo_meta, fps, frames: [{t, objects: [{cls, conf, xyxy}]}]}. Это вход для
facttable-экстрактора (W3): треки → сессии → R1..R10 → verdict.

Запуск: venv/bin/python scripts/infer_w2.py --video open/videos/Х-23.mov \\
        --weights w2_nano/checkpoint_best_ema.pth --out w2_preds/Х-23.json
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np


CLASSES = ["banknotes", "money_bag", "document", "safe", "stamp",
           "outerwear", "terminal"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--weights", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=float, default=1.0, help="частота кадров для инференса")
    ap.add_argument("--threshold", type=float, default=0.4)
    ap.add_argument("--gpu", default="0")
    args = ap.parse_args()

    os.environ.setdefault("CUDA_VISIBLE_DEVICES", args.gpu)
    from rfdetr import RFDETRBase, RFDETRLarge, RFDETRNano, RFDETRSmall
    variant_name = next((v for v in ("nano", "small", "base", "large")
                         if v in args.weights.lower()), "base")
    variant = {"nano": RFDETRNano, "small": RFDETRSmall,
               "base": RFDETRBase, "large": RFDETRLarge}[variant_name]
    try:
        model = variant(pretrain_weights=args.weights)
    except TypeError:
        model = variant(pretrain_weights=args.weights, num_classes=8)

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

    frames = []
    idx = 0
    while True:
        ok, img = cap.read()
        if not ok:
            break
        if idx % step == 0:
            t = idx / fps_native
            dets = model.predict(img, threshold=args.threshold)
            objs = []
            for j in range(len(dets.xyxy)):
                cls = int(dets.class_id[j])
                objs.append({
                    "cls": CLASSES[cls] if 0 <= cls < len(CLASSES) else f"c{cls}",
                    "conf": float(dets.confidence[j]),
                    "xyxy": [float(x) for x in dets.xyxy[j]],
                })
            frames.append({"t": round(t, 3), "objects": objs})
        idx += 1
    cap.release()

    out = {
        "video": os.path.basename(args.video),
        "fps_native": fps_native,
        "fps_infer": args.fps,
        "duration_sec": round(duration, 2),
        "weights": os.path.basename(args.weights),
        "threshold": args.threshold,
        "classes": CLASSES,
        "frames": frames,
    }
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    n_with = sum(1 for fr in frames if fr["objects"])
    print(f"готово: {len(frames)} кадров, {n_with} с детекциями → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
