#!/usr/bin/env python3
"""W2: файнтюн RF-DETR (Apache-2.0) на w1_dataset, 7 классов-примитивов.

Модель видит ТОЛЬКО примитивы; люди/ноуты/кружки на инференсе идут из COCO-весов
(второй проход) или уже готового детектора — этот скрипт учит только наш словарь.

Перед запуском: python3 scripts/merge_w1.py --with-coco  (нужно train|valid + json).
Запуск на neuro (карту под llama-server не трогаем — по умолчанию GPU 1):
  venv/bin/python scripts/train_w2.py --variant nano
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
                    help="CUDA_VISIBLE_DEVICES, напр. 1 (иначе переменная окружения/0)")
    args = ap.parse_args()

    if args.gpu:
        os.environ["CUDA_VISIBLE_DEVICES"] = args.gpu

    for sub in ("train", "valid"):
        j = os.path.join(args.dataset, sub, "_annotations.coco.json")
        if not os.path.isfile(j):
            print(f"нет {j} — сначала: python3 scripts/merge_w1.py --with-coco",
                  file=sys.stderr)
            return 2

    out = args.out or f"{'/'.join(args.dataset.rstrip('/').split('/')[:-1])}/w2_{args.variant}"
    print(f"вариант={args.variant} epochs={args.epochs} batch={args.batch} out={out}")

    import torch
    print("torch:", torch.__version__, "| gpu:", torch.cuda.device_count(),
          "| cuds:", torch.version.cuda)

    from rfdetr import RFDETRBase, RFDETRLarge, RFDETRNano, RFDETRSmall
    variant = {"nano": RFDETRNano, "small": RFDETRSmall,
               "base": RFDETRBase, "large": RFDETRLarge}[args.variant]
    try:
        model = variant()
    except TypeError:  # старые сборки просят num_classes явно
        model = variant(num_classes=8)

    model.train(dataset_dir=args.dataset, epochs=args.epochs, batch_size=args.batch,
                grad_accum_steps=max(1, 16 // args.batch), lr=1e-4, output_dir=out)
    print("готово. чекпоинты/кривые в", out)
    best = os.path.join(out, "checkpoint_best_ema.pth")
    if os.path.isfile(best):
        print("лучший по ema:", best)
    return 0


if __name__ == "__main__":
    sys.exit(main())