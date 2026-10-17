#!/usr/bin/env python3
"""W1 pack: кадры 1 fps по всем роликам (кроме дублей Х-47/Х-48) → w1_frames/<ролик>/.

Имя кадра: <имя ролика>_t<сек.жпс.3>.jpg  (напр. X-1_t000.jpg, Х-13_t047.jpg)
Идемпотентно: существующие кадры не перезаписываются (можно дожимать по частям).
Запуск: python3 scripts/make_w1_frames.py   (аргументов нет — имена кириллические)
"""
import csv
import glob
import os
import sys
import time

import cv2

ROOT = "/home/zhus/Desktop/datathon"
VID_DIR = os.path.join(ROOT, "open", "videos")
OUT_DIR = os.path.join(ROOT, "w1_frames")
LABELS = os.path.join(ROOT, "labels.csv")
JPEG_QUALITY = 95  # аннотирование требует деталей, 464x848 мелкое, размер ок


def load_meta():
    rows = {}
    with open(LABELS, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rows[r["filename"]] = r
    return rows


def main():
    meta = load_meta()
    videos = sorted(glob.glob(os.path.join(VID_DIR, "*.mov")))
    t_all = time.time()
    total = 0
    per_video = []
    for path in videos:
        base = os.path.basename(path)[:-4]  # без .mov, имя как есть (X-1 / Х-...)
        row = meta.get(base + ".mov")
        if row and row["duplicate_of"]:
            print(f"skip дубликат {base}: = {row['duplicate_of']}")
            continue
        out_dir = os.path.join(OUT_DIR, base)
        os.makedirs(out_dir, exist_ok=True)

        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            print(f"!! не открылось {base}", file=sys.stderr)
            continue
        expect = int(float(row["duration_sec"]) * 1) + 1 if row else None

        written = 0
        t0 = time.time()
        next_sec = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            sec = int(round(cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0))
            if sec >= next_sec:  # первый кадр на каждой целой секунде
                name = f"{base}_t{sec:03d}.jpg"
                dst = os.path.join(out_dir, name)
                if not os.path.exists(dst):
                    cv2.imwrite(dst, frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
                written += 1
                next_sec = sec + 1
        cap.release()
        total += written
        flag = "" if (expect is None or written == expect) else (f"  <- ожидалось {expect}")
        per_video.append((base, written))
        print(f"{base:8s}: {written:4d} кадров  ({time.time()-t0:.1f}s){flag}")

    print(f"\nитого {total} кадров по {len(per_video)} роликам за {time.time()-t_all:.0f}s")


if __name__ == "__main__":
    main()