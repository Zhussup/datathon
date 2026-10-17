#!/usr/bin/env python3
"""Офлайн-сборка done-ответа API: фикстура фактов (+ реальное видео для кадров).

Проверяет полный путь сборки (движок -> кадры -> JSON) до подключения перцепции:
    python3 scripts/render_result.py fixtures/Х-15.json open/videos/Х-15.mov result.json
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

import worker  # noqa: E402
from pipeline.facts import FactTable  # noqa: E402


def main() -> int:
    if len(sys.argv) not in (2, 3, 4):
        print(__doc__)
        return 2
    fixture = Path(sys.argv[1])
    video = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    out_path = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    if video is not None and not video.exists():
        print(f"-- видео-файла нет: {video}, кадры выданы не будут")
        video = None

    done = worker.assemble(FactTable.from_spec(str(fixture)), video, deadline=None)

    total_b64 = sum(len(f["image_base64"]) for v in done["violations"] for f in v["evidence_frames"])
    print(f"видео:     {fixture.stem}" + (f" ({video.name})" if video else " (без видео)"))
    print(f"вердикт:   {done['verdict']}")
    for v in done["violations"]:
        frames = ", ".join(f'{f["timestamp_sec"]}s/{len(f["image_base64"]) // 1024} KiB'
                           for f in v["evidence_frames"]) or "кадров вырезать не удалось"
        print(f'  - {v["rule_id"]} @{v["timecode_sec"]}s  {v["type"]}  → кадры: {frames}')
    print(f"размер ответа: ~{(len(json.dumps(done)) - total_b64) // 1024} KiB + {total_b64 // 1024} KiB base64")

    if out_path:
        out_path.write_text(json.dumps(done, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"записано:  {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())