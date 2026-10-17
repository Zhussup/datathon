#!/usr/bin/env python3
"""W2: эвал детектора на holdout (val) + карточки предикшенов для глазной проверки.

Per-class AP (supervision) по valid-сплиту w1_dataset + визуальные карточки в --out
(метры на 21 кадре шумные — смотрим глазами, а не только цифрами).

Запуск: venv/bin/python scripts/eval_w2.py --weights w2_nano/checkpoint_best_ema.pth
"""
import argparse
import json
import os

import cv2
import numpy as np
import supervision as sv

CLASSES = ["banknotes", "money_bag", "document", "safe", "stamp",
           "outerwear", "terminal"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="/home/zhus/datathon/w1_dataset")
    ap.add_argument("--weights", required=True)
    ap.add_argument("--threshold", type=float, default=0.4)
    ap.add_argument("--offset", type=int, default=-1,
                    help="поправка индекса класса предикшена (COCO-сплит у нас с 1)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--previews", type=int, default=8)
    args = ap.parse_args()

    out = args.out or os.path.join(os.path.dirname(args.dataset), "w2_eval")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(args.dataset, "valid", "_annotations.coco.json")) as f:
        gt = json.load(f)
    img_dir = os.path.join(args.dataset, "valid")

    variant_name = next((v for v in ("nano", "small", "base", "large")
                         if v in args.weights.lower()), "base")
    from rfdetr import RFDETRBase, RFDETRLarge, RFDETRNano, RFDETRSmall
    variant = {"nano": RFDETRNano, "small": RFDETRSmall,
               "base": RFDETRBase, "large": RFDETRLarge}[variant_name]
    try:
        model = variant(pretrain_weights=args.weights)
    except TypeError:
        model = variant(pretrain_weights=args.weights, num_classes=8)

    metric = sv.metrics.MeanAveragePrecision()
    anno_by_img: dict[int, list[dict]] = {}
    for a in gt["annotations"]:
        anno_by_img.setdefault(a["image_id"], []).append(a)

    n_imgs = n_true = n_pred = 0
    for im in sorted(gt["images"], key=lambda x: x["id"]):
        img = cv2.imread(os.path.join(img_dir, im["file_name"]))
        dets = model.predict(img, threshold=args.threshold)
        pred = sv.Detections(
            xyxy=dets.xyxy,
            class_id=(dets.class_id + args.offset) if dets.class_id is not None else None,
            confidence=dets.confidence)
        gts = []
        for a in anno_by_img.get(im["id"], []):
            x, y, w, h = a["bbox"]
            gts.append(([x, y, x + w, y + h], a["category_id"] - 1))
        target = sv.Detections(
            xyxy=np.array([g[0] for g in gts], dtype=np.float32),
            class_id=np.array([g[1] for g in gts], dtype=int)
            if gts else np.array([], dtype=int)) if gts else sv.Detections.empty()
        metric.update(np.array([pred]), np.array([target]))
        n_imgs += 1
        n_true += len(target)
        n_pred += len(pred)
        if n_imgs == 1 and len(pred):
            print("калибровка оффсета: первые pred class_id:", dets.class_id[:5],
                  f"(+{args.offset} -> {pred.class_id[:5] if len(pred) else '-'})")
        if n_imgs <= args.previews:
            ann = sv.BoxAnnotator()
            lab = sv.LabelAnnotator()
            texts = [f"{CLASSES[c]} {p:.2f}" for c, p in
                     zip(pred.class_id or [], pred.confidence or [])]
            vis = lab.annotate(ann.annotate(img, pred), pred, texts)
            cv2.imwrite(os.path.join(out, f"pred_{im['file_name']}"), vis)

    res = metric.compute()
    print(f"кадров {n_imgs}, gt {n_true}, pred {n_pred}")
    mAP50 = float(res.get("mAP@50", res.get("mAP50", float("nan"))))
    print("mAP@50:", round(mAP50, 4), "| mAP:", round(float(res.get("mAP", float("nan"))), 4))
    per_class = res.get("mAP@50") and None
    for i, name in enumerate(CLASSES):
        v = res.get(f"mAP@50({name.lower()})")
        if v is None:  # разные версии supervision: ключ 'mAP@50_per_class'
            per = res.get("mAP@50_per_class")
            v = per[i] if per is not None and len(per) > i else None
        print(f"{name:12} AP50: {round(float(v), 4) if v is not None else 'н/д'}")
    print("карточки:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())