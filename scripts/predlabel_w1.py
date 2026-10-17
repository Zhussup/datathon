#!/usr/bin/env python3
"""W1-предразметка кадров детекторной разметки: YOLO-World v2 (open-vocab).

Бегает по w1_frames/<ролик>/*.jpg, пишет w1_preds/<ролик>/<кадр>.txt
в формате YOLO (class cx cy w h, нормированные) с ИНДЕКСАМИ канонических
классов (как в merge_w1.py). Человек потом правит эти боксы, а не рисует с нуля.

Если w1_frames/ пуст, а open/videos/ есть — сначала порезать кадры на сервере
(make_w1_frames.py, нужен cv2) — так не надо переливать 300 МБ по слабому каналу.

AGPL (ultralytics) — инструмент предразметки, в поставку продукта НЕ входит.
Запуск на сервере: venv/bin/python scripts/predlabel_w1.py [--imgsz 864] [--conf 0.25]
"""
import argparse
import glob
import os
import subprocess
import sys

ROOT = "/home/zhus/datathon"
FRAMES = os.path.join(ROOT, "w1_frames")
VIDEOS = os.path.join(ROOT, "open", "videos")
PREDS = os.path.join(ROOT, "w1_preds")
WORLD_PT = os.path.join(ROOT, "weights", "yolov8x-worldv2.pt")

# Порядок = канонические классы (синхронно с merge_w1.py / make_w1_packs.py).
CLASSES = ["banknotes", "money_bag", "document", "safe", "stamp", "outerwear", "terminal"]
# Фразы для open-vocab: на каждую лексему — самый «кликабельный» форм-фактор сверху.
PROMPTS = [
    "banknotes",       # стопка купюр
    "money bag",       # мешок/пакет с деньгами
    "document",        # паспорт/удостоверение в руках
    "safe",            # сейф/кассовый ящик
    "stamp",           # именной штамп
    "jacket",          # снятая верхняя одежда
    "payment terminal",  # терминал пересчёта
]


def ensure_frames() -> None:
    total = len(glob.glob(os.path.join(FRAMES, "*", "*.jpg")))
    if total:
        print(f"кадров уже есть: {total} в {len(os.listdir(FRAMES))} роликах")
        return
    if not os.path.isdir(VIDEOS):
        print(f"{FRAMES} пуст и {VIDEOS} нет — сначала залей кадры: rsync -az --partial w1_frames/ {ROOT}/", file=sys.stderr)
        sys.exit(1)
    print("кадров нет — режу из видео на месте (1 к/с, cv2)...")
    script = os.path.join(ROOT, "scripts", "make_w1_frames.py")
    subprocess.run([sys.executable, script], check=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--imgsz", type=int, default=864, help="сторона инференса, кратна 32")
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--device", default="0")
    ap.add_argument("--force", action="store_true", help="переписать существующие txt")
    args = ap.parse_args()

    from ultralytics import YOLO  # noqa: PLC0415 — venv на сервере

    ensure_frames()
    model = YOLO(WORLD_PT)
    model.set_classes(PROMPTS)

    videos = sorted(d for d in os.listdir(FRAMES) if os.path.isdir(os.path.join(FRAMES, d)))
    os.makedirs(PREDS, exist_ok=True)
    counts = {c: 0 for c in CLASSES}
    devices = [args.device, "cpu"]
    for video in videos:
        outdir = os.path.join(PREDS, video)
        os.makedirs(outdir, exist_ok=True)
        frames = sorted(glob.glob(os.path.join(FRAMES, video, "*.jpg")))
        todo = [f for f in frames if args.force or not os.path.exists(
            os.path.join(outdir, os.path.splitext(os.path.basename(f))[0] + ".txt"))]
        if not todo:
            print(f"{video}: уже размечено, пропуск")
            continue
        print(f"{video}: {len(todo)} кадров...")
        for attempt, device in enumerate(devices):
            try:
                for frame in todo:
                    results = model.predict(frame, imgsz=args.imgsz, conf=args.conf,
                                            device=device, verbose=False)
                    lines = []
                    for box in results[0].boxes:
                        cls = int(box.cls)
                        xc = float(box.xywhn[0][0])
                        yc = float(box.xywhn[0][1])
                        bw = float(box.xywhn[0][2])
                        bh = float(box.xywhn[0][3])
                        lines.append(f"{cls} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}")
                        counts[CLASSES[cls]] += 1
                    stem = os.path.splitext(os.path.basename(frame))[0]
                    with open(os.path.join(outdir, stem + ".txt"), "w", encoding="utf-8") as f:
                        f.writelines(line + "\n" for line in lines)
                break
            except Exception as e:  # OOM на карте под llama-server — второй заход на CPU
                print(f"  device={device} упал: {type(e).__name__}: {e}; попробую {'cpu' if attempt == 0 else 'дальше нечего'}")
                if attempt == len(devices) - 1:
                    return 1

    print("\n--- предразметка готова ---")
    for cls in CLASSES:
        print(f"{cls:12} {counts[cls]}")
    print(f"вывод: {PREDS}/  (далее: scripts/make_w1_packs.py — паки с правкой человеком)")
    return 0


if __name__ == "__main__":
    sys.exit(main())