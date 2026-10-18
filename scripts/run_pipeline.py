#!/usr/bin/env python3
"""Запуск полного пайплайна W2→W3→engine на всех видео.

Использование:
  # на neuro, после W2:
  venv/bin/python scripts/run_pipeline.py \\
    --video-dir open/videos/ \\
    --w2-weights w2_nano/checkpoint_best_ema.pth \\
    --coco-weights /home/zhus/datathon/weights/coco_base.pth \\
    --out-dir w2_preds/ \\
    --w3-out-dir w3_facts/

  # на проде (другой угол) — сначала пробуем W2, если мало детекций — fallback
  venv/bin/python scripts/run_pipeline.py \\
    --video-dir /path/to/test_videos/ \\
    --w2-weights w2_nano/checkpoint_best_ema.pth \\
    --coco-weights /home/zhus/datathon/weights/coco_base.pth \\
    --fallback-coco-only \\
    --out-dir w2_preds/
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str]) -> int:
    print(f"$ {' '.join(cmd)}", flush=True)
    r = subprocess.run(cmd)
    return r.returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video-dir", required=True)
    ap.add_argument("--w2-weights", help="W2 .pth (7 примитивов)")
    ap.add_argument("--coco-weights", help="COCO rfdetr-base (для person)")
    ap.add_argument("--out-dir", default="w2_preds")
    ap.add_argument("--w3-out-dir", default="w3_facts")
    ap.add_argument("--threshold", type=float, default=0.4)
    ap.add_argument("--person-threshold", type=float, default=0.5)
    ap.add_argument("--gpu", default="0")
    ap.add_argument("--limit", type=int, help="прогнать только N видео (для теста)")
    ap.add_argument("--skip-existing", action="store_true",
                    help="не пересчитывать, если JSON уже есть")
    ap.add_argument("--fallback-coco-only", action="store_true",
                    help="если W2 дал мало детекций — fallback на COCO person")
    ap.add_argument("--min-prims-per-frame", type=float, default=0.05,
                    help="если среднее число примитивов на кадр < этого, fallback")
    args = ap.parse_args()

    video_dir = Path(args.video_dir)
    videos = sorted([p for p in video_dir.glob("*.mov")])
    if args.limit:
        videos = videos[:args.limit]
    print(f"найдено {len(videos)} видео", flush=True)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    w3_dir = Path(args.w3_out_dir)
    w3_dir.mkdir(parents=True, exist_ok=True)

    rc = 0
    for i, v in enumerate(videos, 1):
        stem = v.stem
        prims_path = out_dir / f"{stem}.json"
        persons_path = out_dir / f"{stem}.persons.json"
        facts_path = w3_dir / f"{stem}.json"

        if args.skip_existing and prims_path.exists() and persons_path.exists() and facts_path.exists():
            print(f"[{i}/{len(videos)}] {stem}: skip (уже есть)", flush=True)
            continue

        print(f"[{i}/{len(videos)}] {stem}: инференс", flush=True)
        # 1) детекторы
        cmd = [sys.executable, "scripts/infer_w2.py",
               "--video", str(v),
               "--out", str(prims_path),
               "--out-persons", str(persons_path),
               "--fps", "1.0",
               "--threshold", str(args.threshold),
               "--person-threshold", str(args.person_threshold),
               "--gpu", args.gpu]
        if args.w2_weights:
            cmd += ["--weights", args.w2_weights]
        if args.coco_weights:
            cmd += ["--coco-weights", args.coco_weights]
        if run(cmd) != 0:
            print(f"  ! {stem}: infer_w2 упал", flush=True)
            rc = 1
            continue

        # 2) проверка fallback
        if args.fallback_coco_only and prims_path.exists():
            try:
                d = json.load(open(prims_path))
                n_frames = max(1, len(d.get("frames", [])))
                n_dets = sum(len(fr.get("objects", [])) for fr in d.get("frames", []))
                density = n_dets / n_frames
                print(f"  плотность W2: {density:.2f} дет/кадр (порог {args.min_prims_per_frame})",
                      flush=True)
                if density < args.min_prims_per_frame:
                    print(f"  ! низкая плотность — для теста с другим углом потребуется fallback",
                          file=sys.stderr, flush=True)
            except Exception as e:
                print(f"  ! не удалось проверить плотность: {e}", flush=True)

        # 3) w3_facts
        cmd = [sys.executable, "scripts/w3_facts.py",
               "--out", str(facts_path),
               "--video", stem]
        if prims_path.exists():
            cmd += ["--preds", str(prims_path)]
        if persons_path.exists():
            cmd += ["--preds-persons", str(persons_path)]
        if run(cmd) != 0:
            print(f"  ! {stem}: w3_facts упал", flush=True)
            rc = 1
            continue

        # 4) engine → verdict
        cmd = [sys.executable, "scripts/run_verdict.py",
               "--facts", str(facts_path),
               "--out", str(w3_dir / f"{stem}.verdict.json")]
        if run(cmd) != 0:
            print(f"  ! {stem}: engine упал", flush=True)
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
