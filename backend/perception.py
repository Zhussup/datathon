"""Перцепция: видео -> таблица фактов.

Конвейер: видео -> infer_w2.py (W2 + COCO person) -> JSON детекций ->
w3_facts.py -> FactTable. Дальше в worker.assemble: engine + кадры-доказательства.

Требования:
- W2 веса: env W2_WEIGHTS (по умолчанию ../w2_nano/checkpoint_best_ema.pth)
- COCO веса: env COCO_WEIGHTS (rfdetr-base COCO для person)
- GPU: env CUDA_VISIBLE_DEVICES (по умолчанию 0)
- Бюджет: deadline мониторится на каждом шаге; при истечении — ProcessingTimeout.

Поведение при ошибке любой стадии:
- Нет весов / нет CUDA — PerceptionUnavailable (как и раньше, job -> failed).
- W2 дал 0 детекций — оставляем попытку, w3_facts заполнит пустые маски,
  engine выдаст no_violation (это легитимный «не нашли»).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

from pipeline.facts import FactTable

# бюджеты
INFER_BUDGET_SEC = 180.0  # детекция — основной риск по времени
W3_BUDGET_SEC = 30.0      # маппинг фактов — почти мгновенный

# пути
_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = _ROOT / "scripts"
_DEFAULT_W2 = _ROOT / "w2_nano" / "checkpoint_best_ema.pth"
_DEFAULT_COCO = _ROOT / "weights" / "rfdetr_base_coco.pth"


class PerceptionUnavailable(RuntimeError):
    """Перцепция не готова обработать это видео."""


def _check_deadline(deadline: float | None, label: str) -> None:
    if deadline is not None and time.monotonic() >= deadline:
        from worker import ProcessingTimeout  # local import: цикл избежим
        raise ProcessingTimeout(f"{label}: бюджет истёк")


def _w2_weights() -> str:
    p = os.environ.get("W2_WEIGHTS") or str(_DEFAULT_W2 if _DEFAULT_W2.exists() else "")
    if not p or not Path(p).exists():
        raise PerceptionUnavailable(
            f"не найдены W2-веса ({p}); задайте W2_WEIGHTS=/path/to/checkpoint_best_ema.pth")
    return p


def _coco_weights() -> str | None:
    """'auto'/unset → 'auto' (rfdetr сам скачает базу COCO);
    'off'/'none'/'0' → None (person-детектор отключен); иначе путь."""
    p = os.environ.get("COCO_WEIGHTS", "auto").strip().lower()
    if p in ("", "auto"):
        return "auto"
    if p in ("off", "none", "0"):
        return None
    if Path(p).exists():
        return p
    if _DEFAULT_COCO.exists():
        return str(_DEFAULT_COCO)
    return "auto"  # лучшее, что умеем: пусть rfdetr скачает сам


def _run(cmd: list[str], deadline: float | None, label: str) -> None:
    """Запуск подпроцесса с poll-проверкой дедлайна."""
    print(f"[perception] {label}: {' '.join(cmd)}", flush=True)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        while proc.poll() is None:
            _check_deadline(deadline, label)
            time.sleep(0.5)
        rc = proc.wait()
        if proc.stdout:
            tail = proc.stdout.read()[-2000:] if hasattr(proc.stdout, "read") else ""
            if tail:
                print(f"[perception] {label} tail: {tail}", flush=True)
        if rc != 0:
            raise PerceptionUnavailable(f"{label}: exit code {rc}")
    except BaseException:
        proc.kill()
        proc.wait()
        raise
    _check_deadline(deadline, label)


def extract_facts(video_path: Path, deadline: float | None = None):
    """Видео -> FactTable. Бюджет: INFER_BUDGET_SEC + W3_BUDGET_SEC."""
    if not video_path.exists():
        raise PerceptionUnavailable(f"нет видео: {video_path}")

    # Деморежим (UI без детектора, тесты): факты читаются из готовой фикстуры.
    demo = os.environ.get("PIPELINE_DEMO_FACTS")
    if demo:
        if not Path(demo).exists():
            raise PerceptionUnavailable(f"файл демо-фикстуры не найден: {demo}")
        from pipeline.facts import FactTable as _FT
        return _FT.from_spec(demo)

    w2 = _w2_weights()
    coco = _coco_weights()
    if deadline is not None:
        infer_deadline = min(deadline, time.monotonic() + INFER_BUDGET_SEC)
    else:
        infer_deadline = time.monotonic() + INFER_BUDGET_SEC

    job_id = uuid.uuid4().hex
    tmp = Path(os.environ.get("PERCEPTION_TMP", "/tmp")) / f"perception_{job_id}"
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        prims = tmp / "prims.json"
        persons = tmp / "persons.json"
        facts = tmp / "facts.json"

        # 1) детекция (W2 + COCO person)
        cmd = [sys.executable, str(_SCRIPTS / "infer_w2.py"),
               "--video", str(video_path),
               "--out", str(prims),
               "--out-persons", str(persons),
               "--fps", "1.0",
               "--threshold", os.environ.get("W2_THRESHOLD", "0.4"),
               "--person-threshold", os.environ.get("PERSON_THRESHOLD", "0.5"),
               "--gpu", os.environ.get("CUDA_VISIBLE_DEVICES", "0")]
        cmd += ["--weights", w2]
        if coco:
            cmd += ["--coco-weights", coco]
        _run(cmd, infer_deadline, "infer_w2")

        # 2) w3_facts -> JSON
        _check_deadline(deadline, "w3_facts")
        cmd = [sys.executable, str(_SCRIPTS / "w3_facts.py"),
               "--out", str(facts),
               "--video", video_path.name]
        if prims.exists():
            cmd += ["--preds", str(prims)]
        if persons.exists():
            cmd += ["--preds-persons", str(persons)]
        _run(cmd, deadline, "w3_facts")

        # 3) JSON -> FactTable
        if not facts.exists():
            raise PerceptionUnavailable("w3_facts не записал файл")
        return FactTable.from_spec(str(facts))
    finally:
        # чистим временные JSON-ы (видео остаётся в storage, как и раньше)
        try:
            for p in tmp.glob("*.json"):
                p.unlink()
            tmp.rmdir()
        except OSError:
            pass
