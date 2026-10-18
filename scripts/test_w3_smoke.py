#!/usr/bin/env python3
"""Smoke-test W3: фейковые детекции имитируют Х-15 (R2 @15 с).

Сценарий: в кадре есть кассир, приходит клиент, кассир отлучается
(cashier_away 12..18 с), banknotes лежит на столе всё это время.
Ожидаем: R2 @12..18 с.

Запуск: python3 scripts/test_w3_smoke.py
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.w3_facts import merge_frames  # type: ignore
from pipeline.facts import FactTable
from pipeline.engine import run_engine


def make_frame(t: float, prims: list[dict], persons: list[dict]) -> dict:
    return {"t": t, "prims": prims, "persons": persons}


def gen_X15_scenario() -> list[dict]:
    """Имитируем Х-15: 30 секунд, 1 fps. Кадры 0..29.

    - 0..6 с: client_present (кассир у прилавка + клиент над прилавком)
    - 7..11 с: только кассир (клиент ушёл)
    - 12..18 с: cashier_away (никого в кадре), banknotes_on_desk
    - 19..29 с: только кассир вернулся
    """
    frames = []
    # кадр 464x848; cy > 0.5 = у прилавка, cy <= 0.5 = над прилавком
    box_cashier = [150, 480, 280, 700]    # cy=0.695 (у прилавка)
    box_client = [50, 350, 180, 450]     # cy=0.471 (над прилавком)
    box_banknotes = [180, 460, 280, 510]  # в зоне кассира

    for t in range(30):
        persons, prims = [], []
        if t < 7:  # кассир + клиент
            persons = [
                {"cls": "person", "conf": 0.9, "xyxy": box_cashier},
                {"cls": "person", "conf": 0.9, "xyxy": box_client},
            ]
        elif t < 12:  # только кассир
            persons = [{"cls": "person", "conf": 0.9, "xyxy": box_cashier}]
        elif t < 19:  # cashier_away
            pass
        else:  # только кассир вернулся
            persons = [{"cls": "person", "conf": 0.9, "xyxy": box_cashier}]
        if 3 <= t < 6:  # doc_check
            prims.append({"cls": "document", "conf": 0.9, "xyxy": [180, 440, 240, 500]})
        if 5 <= t < 7:  # money_handover (banknotes в зоне кассира появился)
            prims.append({"cls": "banknotes", "conf": 0.9, "xyxy": box_banknotes})
        if 7 <= t < 28:
            prims.append({"cls": "banknotes", "conf": 0.9, "xyxy": box_banknotes})
        frames.append({"t": float(t), "prims": prims, "persons": persons})
    return frames


def to_preds_dict(frames: list[dict]) -> tuple[dict, dict]:
    prims = {
        "video": "Х-15-fake", "duration_sec": 30.0, "classes": ["banknotes"],
        "frames": [{"t": fr["t"], "objects": fr["prims"]} for fr in frames if fr["prims"]],
    }
    persons = {
        "video": "Х-15-fake", "duration_sec": 30.0, "classes": ["person"],
        "frames": [{"t": fr["t"], "objects": fr["persons"]} for fr in frames if fr["persons"]],
    }
    return prims, persons


def main() -> int:
    frames = gen_X15_scenario()
    prims, persons = to_preds_dict(frames)

    with tempfile.TemporaryDirectory() as d:
        p_path = os.path.join(d, "prims.json")
        q_path = os.path.join(d, "persons.json")
        f_path = os.path.join(d, "facts.json")
        json.dump(prims, open(p_path, "w"))
        json.dump(persons, open(q_path, "w"))
        # прогоняем как subprocess
        import subprocess
        r = subprocess.run([
            sys.executable, "scripts/w3_facts.py",
            "--preds", p_path, "--preds-persons", q_path,
            "--out", f_path,
        ], capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        print("w3_facts stdout:", r.stdout)
        if r.returncode != 0:
            print("w3_facts stderr:", r.stderr, file=sys.stderr)
            return r.returncode
        ft = FactTable.from_spec(f_path)
        result = run_engine(ft)
        print("verdict:", result["verdict"])
        for v in result["violations"]:
            print(f"  {v['rule_id']} @ {v['timecode_sec']}s — {v['type']} ({v['npa']})")
        return 0


if __name__ == "__main__":
    sys.exit(main())
