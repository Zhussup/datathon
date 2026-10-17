"""Движок проверки: один проход правил по таблице фактов.

Правила (rules.RULES) — декларативные данные; движок о смысле не знает:
триггер -> вопрос -> событие -> merge -> вердикт. Всё, что калибруется
(окна, пороги, мосты сессий), живёт в Config и constants facts.py.
"""
from __future__ import annotations

from .facts import FactTable
from .rules import RULES, Config, Event, Rule

MERGE_NEAR_SEC = 3.0  # срабатывания одного правила ближе 3 c — один дубль события


def merge_events(events: list[Event]) -> list[Event]:
    """Дубликаты одного правила слить, разные типы оставить (ТЗ: несколько нарушений)."""
    out: list[Event] = []
    for e in sorted(events, key=lambda e: (e.timecode, e.rule_id)):
        if out and out[-1].rule_id == e.rule_id and abs(e.timecode - out[-1].timecode) <= MERGE_NEAR_SEC:
            continue
        out.append(e)
    return out


def event_to_api(e: Event) -> dict:
    """Раздел 10 ТЗ: type, timecode_sec, description, evidence_frames.

    image_base64 добирается этапом выгрузки кадров (ffmpeg -ss); пока — таймстемпы.
    npa/confident/rule_id — служебные поля для UI и калибровки (жюри не мешают).
    """
    return {
        "type": e.type_name,
        "timecode_sec": round(e.timecode, 1),
        "description": e.description,
        "evidence_frames": [{"timestamp_sec": round(ts, 1)} for ts in e.frames],
        "npa": e.npa,
        "confident": e.confident,
        "rule_id": e.rule_id,
    }


def run_rules_for_rule(rule_obj: Rule, ft: FactTable, cfg: Config) -> list[Event]:
    found: list[Event] = []
    for anchor in rule_obj.trigger(ft, cfg):
        ev = rule_obj.evaluate(ft, anchor, cfg)
        if ev is not None:
            found.append(ev)
    return found


def run_engine(ft: FactTable, cfg: Config | None = None) -> dict:
    cfg = cfg or Config()
    found: list[Event] = []
    for r in RULES:
        found.extend(run_rules_for_rule(r, ft, cfg))
    events = merge_events(found)
    return {
        "video": ft.video,
        "verdict": "violation" if events else "no_violation",
        "violations": [event_to_api(e) for e in events],
        "_events": events,
    }