#!/usr/bin/env python3
"""Сборка общего W1-датасета из разметки команды.

Вход:  w1_frames/<ролик>/<кадр>.jpg            (кадры, make_w1_frames.py)
       w1_out/<ролик>/<кадр>.txt               (YOLO-разметка экспортированная тимейтами)
       w1_out/<ролик>/classes.txt (опц.)       (порядок классов у разметчика; иначе — канон)
Выход: w1_dataset/  (images/{train,val}, labels/{train,val}, data.yaml) + статистика.

Формат строки txt: <class_idx> x1 y1 x2 y2 (нормированные координаты).
- --boxes-format xywh  (по умолчанию: центр+ширина+высота, стандарт Ultralytics)
- --boxes-format xyxy  (угловые точки, если инструмент экспортирует так)

Сплит строго по роликам: holdout (см. W1_PROTOCOL) → val, остальные → train.
Дубли Х-47/Х-48 в датасет не попадают никогда.
Запуск: python3 scripts/merge_w1.py
"""
import argparse
import glob
import os
import shutil
import sys

import cv2  # размеры/вёрстка кадров для --with-coco

ROOT = "/home/zhus/Desktop/datathon"

# Один источник правды по классам — как в scripts/make_w1_packs.py (синхронизируем руками).
CLASSES = ["banknotes", "money_bag", "document", "safe", "stamp", "outerwear", "terminal"]

# Синхронно с W1_PROTOCOL.md.
HOLDOUT = {"Х-3", "Х-11", "Х-16", "Х-26", "Х-34", "Х-40"}
EXCLUDE_DUPS = {"Х-47", "Х-48"}

FRAMES = os.path.join(ROOT, "w1_frames")
OUT_SRC = os.path.join(ROOT, "w1_out")
DATASET = os.path.join(ROOT, "w1_dataset")


def norm_dirname(name: str) -> str:
    """'X-1' (латиница) и 'Х-1' (кириллица) — один ролик; ключ = номер."""
    digits = "".join(ch for ch in name if ch.isdigit())
    return f"#{int(digits)}" if digits else name


def read_classes(path: str) -> list[str]:
    try:
        with open(path, encoding="utf-8-sig") as f:
            names = [line.strip() for line in f if line.strip()]
        if names:
            return names
    except OSError:
        pass
    return []


def parse_box(parts: list[str], fmt: str) -> tuple[str, list[float]] | None:
    idx = parts[0]
    try:
        v = [float(x) for x in parts[1:5]]
    except ValueError:
        return None
    if len(v) != 4:
        return None
    if fmt == "xyxy":  # угловые -> центр/размер
        x1, y1, x2, y2 = v
        cx, cy, w, h = (x1 + x2) / 2, (y1 + y2) / 2, abs(x2 - x1), abs(y2 - y1)
    else:
        cx, cy, w, h = v
    return idx, [cx, cy, w, h]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--boxes-format", choices=("xywh", "xyxy"), default="xywh")
    ap.add_argument("--dry", action="store_true", help="только статистика, датасет не писать")
    ap.add_argument("--with-coco", action="store_true",
                    help="дополнительно собрать дерево под RF-DETR: "
                         "w1_dataset/train|valid с _annotations.coco.json")
    args = ap.parse_args()

    videos = {}
    for name in sorted(os.listdir(OUT_SRC)):
        path = os.path.join(OUT_SRC, name)
        if os.path.isdir(path):
            videos[name] = path
    if not videos:
        print("в w1_out/ нет папок роликов", file=sys.stderr)
        return 2

    stats = {}
    problems = []
    name_map = {norm_dirname(v): v for v in videos}
    for video, path in sorted(videos.items(), key=lambda kv: (norm_dirname(kv[0]), kv[0])):
        txts = sorted(glob.glob(os.path.join(path, "*.txt")))
        txts = [t for t in txts if os.path.basename(t) != "classes.txt"]
        local = read_classes(os.path.join(path, "classes.txt"))
        if local and len(videos) > 1 and set(local) != set(CLASSES):
            problems.append(f"{video}: classes.txt не совпадает с каноном: {local}")
        mapping = {str(CLASSES.index(n)): n for n in CLASSES}  # канон по умолчанию
        if local:
            canon = {str(i): n for i, n in enumerate(local) if n in CLASSES}
            if len(canon) == len(local):
                mapping = canon
            else:
                problems.append(
                    f"{video}: classes.txt отличен от канона — собираю по канону по индексам, СВЕРЬ ВРУЧНУЮ"
                )

        split = "val" if norm_dirname(video) in {norm_dirname(h) for h in HOLDOUT} else "train"
        if norm_dirname(video) in {norm_dirname(e) for e in EXCLUDE_DUPS}:
            problems.append(f"{video}: дубликат — в датасет не идёт")
            continue

        boxes, empty = 0, 0
        for txt in txts:
            stem = os.path.splitext(os.path.basename(txt))[0]
            lines_out = []
            with open(txt, encoding="utf-8") as f:
                for line_no, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split()
                    parsed = parse_box(parts, args.boxes_format)
                    if parsed is None:
                        problems.append(f"{video}/{stem}: строка {line_no} не парсится: {line!r}")
                        continue
                    idx, (cx, cy, w, h) = parsed
                    cls = mapping.get(idx)
                    if cls is None:
                        problems.append(f"{video}/{stem}: класс {idx} неизвестен (строка {line_no})")
                        continue
                    if not (0 <= cx <= 1 and 0 <= cy <= 1 and 0 < w <= 1.5 and 0 < h <= 1.5):
                        problems.append(f"{video}/{stem}: бокс вне кадра (строка {line_no}): {line!r}")
                        continue
                    lines_out.append(
                        f"{CLASSES.index(cls)} {cx:.6f} {cy:.6f} {min(w, 1):.6f} {min(h, 1):.6f}"
                    )
                    boxes += 1
            if not lines_out:
                empty += 1
            key = (split, video, stem)
            stats.setdefault(key, []).extend(lines_out)

        # Кадры без разметки (бэкграунд) — все кадры ролика, у которых нет txt.
        frames_dir = os.path.join(FRAMES, video)
        for img in sorted(glob.glob(os.path.join(frames_dir, "*.jpg"))):
            stem = os.path.splitext(os.path.basename(img))[0]
            stats.setdefault((split, video, stem), [])
        annotated = {s for (_, v, s) in stats if v == video}
        print(f"{video}: {len(txts)} txt, {boxes} боксов, {empty} пустых, split={split}")

    counts = {c: {"train": 0, "val": 0} for c in CLASSES}
    for (split, _, _), lines in stats.items():
        for line in lines:
            counts[CLASSES[int(line.split()[0])]][split] += 1
    imgs_count = {"train": len({(s, v, k) for (s, v, k) in stats if s == "train"}),
                  "val": len({(s, v, k) for (s, v, k) in stats if s == "val"})}
    print("\n--- по классам (инстансов) ---")
    for cls in CLASSES:
        t, v = counts[cls]["train"], counts[cls]["val"]
        flag = "  <- МАЛО" if t < 40 else ""
        print(f"{cls:12} train {t:5}  val {v:5}{flag}")
    print(f"кадров: train {imgs_count['train']}, val {imgs_count['val']}")

    if args.dry:
        print("\n(--dry: датасет не записан)")
        return 0

    problems_final = list(problems)
    for split in ("train", "val"):
        os.makedirs(os.path.join(DATASET, "images", split), exist_ok=True)
        os.makedirs(os.path.join(DATASET, "labels", split), exist_ok=True)
        for (split2, video, stem), lines in stats.items():
            if split2 != split:
                continue
            frame = os.path.join(FRAMES, video, stem + ".jpg")
            if not os.path.exists(frame):
                problems_final.append(f"{video}/{stem}: txt без кадра — пропущен")
                continue
            shutil.copy2(frame, os.path.join(DATASET, "images", split, stem + ".jpg"))
            with open(os.path.join(DATASET, "labels", split, stem + ".txt"), "w", encoding="utf-8") as f:
                f.writelines(line + "\n" for line in lines)

    with open(os.path.join(DATASET, "data.yaml"), "w", encoding="utf-8") as f:
        f.write(f"path: {DATASET}\ntrain: images/train\nval: images/val\n"
                f"names: {CLASSES}\n")
    print(f"\nдатасет собран: {DATASET}")

    if args.with_coco:
        # Дерево под RF-DETR (Roboflow-конвенция): train/ и valid/ с картинками
        # рядом и _annotations.coco.json (category_id с 1). ~15 МБ дублей картинок.
        import json
        H, W = cv2.imread(
            sorted(glob.glob(os.path.join(FRAMES, "*", "*.jpg")))[0]).shape[:2]
        cats = [{"id": i + 1, "name": n} for i, n in enumerate(CLASSES)]
        for split, subset in (("train", "train"), ("val", "valid")):
            outdir = os.path.join(DATASET, subset)
            os.makedirs(outdir, exist_ok=True)
            images, annos, imgs_n, annos_n = [], [], 1, 1
            for (split2, _video, stem), lines in sorted(stats.items()):
                if split2 != split:
                    continue
                frame = os.path.join(FRAMES, _video, stem + ".jpg")
                if not os.path.exists(frame):
                    continue  # уже помечено в problems_final выше
                shutil.copy2(frame, os.path.join(outdir, stem + ".jpg"))
                images.append({"id": imgs_n, "file_name": stem + ".jpg",
                               "width": W, "height": H})
                for line in lines:
                    c, cx, cy, w, h = line.split()
                    cx, cy, w, h = (float(x) for x in (cx, cy, w, h))
                    px, py, pw, ph = (cx - w / 2) * W, (cy - h / 2) * H, w * W, h * H
                    annos.append({"id": annos_n, "image_id": imgs_n,
                                  "category_id": int(c) + 1,
                                  "bbox": [px, py, pw, ph], "area": pw * ph,
                                  "iscrowd": 0})
                    annos_n += 1
                imgs_n += 1
            with open(os.path.join(outdir, "_annotations.coco.json"), "w") as f:
                json.dump({"images": images, "annotations": annos,
                           "categories": cats}, f)
            print(f"coco/{subset}: {len(images)} картинок, {len(annos)} боксов")
    if problems_final:
        print(f"\n--- проблемы ({len(problems_final)}) ---")
        for p in problems_final[:40]:
            print(" ", p.encode("ascii", "replace").decode())
        if len(problems_final) > 40:
            print(f"  ... и ещё {len(problems_final) - 40}")
    return 0


if __name__ == "__main__":
    sys.exit(main())