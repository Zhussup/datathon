#!/usr/bin/env python3
"""W2: файнтюн RF-DETR (Apache-2.0) на w1_dataset, 7 классов-примитивов.

Модель видит ТОЛЬКО примитивы; люди/ноуты/кружки на инференсе идут из COCO-весов
(второй проход) или уже готового детектора — этот скрипт учит только наш словарь.

Перед запуском: python3 scripts/merge_w1.py --with-coco  (нужно train|valid + json).
Запуск на neuro (1 GPU):
  venv/bin/python scripts/train_w2.py --variant nano --gpu 0
Запуск на 2 GPU (DDP через torchrun — ускоряет ~1.7×, не идеально ×2):
  torchrun --nproc_per_node=2 scripts/train_w2.py --variant nano
Чекпоинты и кривые: --out (по умолчанию w2_<variant> рядом с датасетом).
"""
import argparse
import os
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="/home/zhus/datathon/w1_dataset")
    ap.add_argument("--variant", default="nano",
                    choices=("nano", "small", "base", "large"))
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--out", default=None)
    ap.add_argument("--gpu", default=None,
                    help="CUDA_VISIBLE_DEVICES для single-GPU; для DDP запускать через torchrun")
    args = ap.parse_args()

    # single-GPU: фильтруем карту
    if args.gpu:
        os.environ["CUDA_VISIBLE_DEVICES"] = args.gpu
    # DDP: torchrun выставит LOCAL_RANK/RANK/WORLD_SIZE
    world_size = int(os.environ.get("WORLD_SIZE", "1"))
    local_rank = int(os.environ.get("LOCAL_RANK", "0"))

    for sub in ("train", "valid"):
        j = os.path.join(args.dataset, sub, "_annotations.coco.json")
        if not os.path.isfile(j):
            print(f"нет {j} — сначала: python3 scripts/merge_w1.py --with-coco",
                  file=sys.stderr)
            return 2

    out = args.out or f"{'/'.join(args.dataset.rstrip('/').split('/')[:-1])}/w2_{args.variant}"
    if local_rank == 0:
        print(f"вариант={args.variant} epochs={args.epochs} batch={args.batch} "
              f"world={world_size} out={out}", flush=True)

    import torch
    if local_rank == 0:
        print("torch:", torch.__version__, "| gpu:", torch.cuda.device_count(),
              "| cuds:", torch.version.cuda, flush=True)

    from rfdetr import RFDETRBase, RFDETRLarge, RFDETRNano, RFDETRSmall
    variant = {"nano": RFDETRNano, "small": RFDETRSmall,
               "base": RFDETRBase, "large": RFDETRLarge}[args.variant]
    try:
        model = variant()
    except TypeError:  # старые сборки просят num_classes явно
        model = variant(num_classes=8)

    if world_size > 1:
        # DDP: увеличиваем эффективный батч
        eff_batch = args.batch * world_size
        if local_rank == 0:
            print(f"DDP: world={world_size}, effective batch={eff_batch}", flush=True)
    else:
        eff_batch = args.batch

    model.train(dataset_dir=args.dataset, epochs=args.epochs, batch_size=eff_batch,
                grad_accum_steps=max(1, 16 // eff_batch), lr=1e-4, output_dir=out)
    if local_rank == 0:
        print("готово. чекпоинты/кривые в", out, flush=True)
        best = os.path.join(out, "checkpoint_best_ema.pth")
        if os.path.isfile(best):
            print("лучший по ema:", best, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())