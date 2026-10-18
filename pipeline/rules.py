"""Десять правил как данные + пороги. Код-зеркало карточек rules_tree.html.

Каждое правило: триггер (где в таймлайне правило вообще спрашивается), единственный
вопрос о контексте и два исхода. Срабатывание -> Event с типом, таймкодом, кадрами
и пунктом НПА из law.md. У R4/R5/R8 прямого пункта нет — npa=None, тип честно
подаётся как «признак», без выдуманных ссылок (критерий 4).

Форма якорей у триггеров:
- order-правила: (t, t) для событий; Session для R4; (t, run, inner_enter) для R9;
- streak-правила: (t0, t1) — отрезки страйка маски.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .facts import FactTable, Session

# ---------- пункты НПА (полные цитаты и сверка — law.md) ----------

NPA_R1 = "Правила № 231 (НБ РК, V1900019680), п. 19 пп. 1; при выдаче — п. 31 пп. 1"
NPA_R2 = "Правила № 231, п. 20 абз. 2"
NPA_R3 = "Правила № 231, п. 20 и п. 76; Правила № 14, п. 16 пп. 1"
NPA_R6 = "Правила № 231, п. 20 абз. 1"
NPA_R7 = "Правила № 231, п. 12"
NPA_R9 = "Правила № 14, п. 8 и п. 16 пп. 1"
NPA_R10 = "Правила № 231, п. 19 (ред. № 19 от 28.02.2022)"

# ---------- типы нарушений (то, что уходит в API "type") ----------

T_R1 = "Приём денег без проверки документа"
T_R2 = "Безнадзорные ценности"
T_R3 = "Сейф или ключ без присмотра при уходе"
T_R4 = "Признак: деньги клиента не выданы"
T_R5 = "Признак: обслуживание двух клиентов одновременно"
T_R6 = "Пересчёт в отсутствие клиента"
T_R7 = "Личные вещи в кассовом узле"
T_R8 = "Признак: нарушение порядка рабочего места"
T_R9 = "Кассовая зона не закрыта"
T_R10 = "Приём без пересчёта и оформления"
T_R11 = "Деньги не убраны при приёме следующего клиента"


@dataclass
class Config:
    """Черновые пороги (rules_tree.html, «Крутящие ручки»). Калибруются на данных."""
    doc_window: float = 45.0  # R1: окно поиска doc_check до money_handover, если сессии нет
    r4_count_look: float = 8.0  # R4: подавить, если пересчёт продолжается после ухода (это R6)
    r4_present: float = 1.5  # R4: деньги должны лежать сразу после ухода клиента
    r5_min: float = 2.0      # R5: два клиента в кадре ≥ 2 c
    r6_look: float = 5.0     # R6: клиент отсутствует в окне [t, t+5]
    np_min: float = 2.5      # R2: безнадзорность ≥ 2.5 c (Х-15: пустой кадр+мешок ~3 с)
    r7_min: float = 10.0     # R7: личные вещи на столе ≥ 10 c
    r8_min: float = 5.0      # R8: штампы/экран при уходе ≥ 5 c
    r9_min: float = 5.0      # R9: дверь открыта ≥ 5 c
    r10_back: float = 60.0   # R10: money_to_safe ищет money_handover не дальше назад
    r11_grace: float = 2.0   # R11: банкноты на столе в окне [t0-1, t0+grace] нового клиента
    r11_stale: float = 10.0  # R11: деньги «старые», если handover был раньше чем за 10 c до
    r11_gap: float = 7.0     # R11: person_enter ближе 7 c — один и тот же эпизод


@dataclass(frozen=True)
class Event:
    rule_id: str
    type_name: str
    timecode: float
    frames: list[float]          # таймстемпы кадров-доказательств (images доберёт выгрузка)
    npa: str | None
    confident: bool              # False → «признак», без правовой квалификации
    description: str


@dataclass(frozen=True)
class Rule:
    id: str
    kind: str                    # "order" | "streak"
    type_name: str
    npa: str | None
    confident: bool
    trigger: Callable[[FactTable, Config], list]
    evaluate: Callable[[FactTable, object, Config], Event | None]


RULES: list[Rule] = []


def rule(rid, kind, type_name, npa, confident, trigger, evaluate) -> None:
    RULES.append(Rule(rid, kind, type_name, npa, confident, trigger, evaluate))


def _trig_events(name: str):
    def trig(ft: FactTable, cfg: Config) -> list[tuple[float, float]]:
        return [(t, t) for t in ft.event_times(name)]
    return trig


def _streak_frames(ft: FactTable, t0: float, t1: float) -> list[float]:
    mid = (t0 + t1) / 2
    return [round(t0, 1), round(min(mid, ft.duration), 1), round(max(t0, t1 - 0.5), 1)]


# ---------- R1 Документ раньше денег -----------------------------------------

def _r1_eval(ft, anchor, cfg):
    t = anchor[0]
    sess = ft.active_session(t)
    t0 = sess.t0 if sess else t - cfg.doc_window
    if ft.first_event("doc_check", t0, t) is not None:
        return None
    return Event("R1", T_R1, t, [round(t, 1), round(min(t + 0.5, ft.duration), 1)], NPA_R1, True,
                 f"Деньги передаются кассиру на {t:.1f} с, а проверка документа клиента с начала "
                 f"визита ({t0:.1f} с) не зафиксирована. Идентификация должна предшествовать приёму денег.")


rule("R1", "order", T_R1, NPA_R1, True, _trig_events("money_handover"), _r1_eval)


# ---------- R2 Безнадзорные ценности ------------------------------------------

def _r2_trig(ft, cfg):
    m = ft.mask_and(ft.mask_or("banknotes_on_desk", "money_bag_on_desk"), ft.mask("cashier_away"))
    return ft.streaks_from_mask(m, cfg.np_min)


def _r2_eval(ft, anchor, cfg):
    t0, t1 = anchor
    return Event("R2", T_R2, t0, _streak_frames(ft, t0, t1), NPA_R2, True,
                 f"Ценности (банкноты/мешок) остаются на рабочей поверхности при кассире, отошедшем "
                 f"от стола: {t0:.1f}-{t1:.1f} с ({t1 - t0:.0f} с). Ранее принятые наличные должны "
                 f"храниться в закрывающемся на ключ устройстве.")


rule("R2", "streak", T_R2, NPA_R2, True, _r2_trig, _r2_eval)


# ---------- R3 Сейф при уходе --------------------------------------------------

def _r3_eval(ft, anchor, cfg):
    t = anchor[0]
    safe = ft.state_at("safe_open", t)
    key = ft.state_at("key_in_lock", t)
    if not (safe or key):
        return None
    what = " сейф не закрыт" if safe else ""
    if key:
        what += " и ключ оставлен в замке" if safe else " ключ оставлен в замке"
    return Event("R3", T_R3, t, [round(t, 1), round(min(t + 0.5, ft.duration), 1)], NPA_R3, True,
                 f"Кассир отходит от рабочего места на {t:.1f} с, при этом{what}.")


rule("R3", "order", T_R3, NPA_R3, True, _trig_events("walk_away"), _r3_eval)


# ---------- R4 Деньги не вернулись клиенту (признак) ---------------------------

def _r4_trig(ft, cfg):
    return [s for s in ft.sessions() if not s.open_end]


def _r4_eval(ft, sess, cfg):
    end = sess.t1
    if not ft.any_event("count_start", sess.t0, end):
        return None  # при клиенте деньги не считали → домен R10/R2, не «невыдача»
    m = ft.mask_or("banknotes_on_desk", "money_bag_on_desk")
    i0 = ft.tick_index(end)
    i1 = ft.tick_index(min(end + cfg.r4_present, ft.duration))
    if not any(m[i] for i in range(i0, i1 + 1)):
        return None
    if ft.any_event("count_start", end, end + cfg.r4_count_look):
        return None  # пересчёт продолжается после ухода — это ситуация R6
    return Event("R4", T_R4, end, [round(end, 1), round(min(end + 0.5, ft.duration), 1)], None, False,
                 f"Обслуживание клиента завершается на {end:.1f} с, а пачка банкнот остаётся на "
                 f"рабочей поверхности; выдача клиенту или уборка на хранение на видео не видны. "
                 f"Требует проверки человеком.")


rule("R4", "order", T_R4, None, False, _r4_trig, _r4_eval)


# ---------- R5 Два клиента сразу (признак) --------------------------------------

def _r5_trig(ft, cfg):
    return ft.streaks("clients_2plus", cfg.r5_min)


def _r5_eval(ft, anchor, cfg):
    t0, t1 = anchor
    return Event("R5", T_R5, t0, [round(t0, 1), round(min(t1, ft.duration), 1)], None, False,
                 f"У стойки одновременно находятся два человека ({t0:.1f}-{t1:.1f} с, "
                 f"≥{cfg.r5_min:.0f} с). Признак параллельного обслуживания двух клиентов.")


rule("R5", "streak", T_R5, None, False, _r5_trig, _r5_eval)


# ---------- R6 Пересчёт в отсутствие клиента ------------------------------------

def _r6_eval(ft, anchor, cfg):
    t = anchor[0]
    i0 = ft.tick_index(t)
    i1 = ft.tick_index(min(t + cfg.r6_look, ft.duration))
    if any(ft.mask("client_present")[i] for i in range(i0, i1 + 1)):
        return None
    return Event("R6", T_R6, t, [round(t, 1), round(min(t + 0.5, ft.duration), 1)], NPA_R6, True,
                 f"Пересчёт купюр на {t:.1f} с идёт в отсутствие клиента (клиент не появляется "
                 f"следующие {cfg.r6_look:.0f} с). Пересчёт проводится в присутствии клиента.")


rule("R6", "order", T_R6, NPA_R6, True, _trig_events("count_start"), _r6_eval)


# ---------- R7 Личные вещи на кассовом столе -------------------------------------

def _r7_trig(ft, cfg):
    return ft.streaks_from_mask(ft.mask_or("outerwear_on_desk", "bag_on_desk"), cfg.r7_min)


def _r7_eval(ft, anchor, cfg):
    t0, t1 = anchor
    return Event("R7", T_R7, t0, _streak_frames(ft, t0, t1), NPA_R7, True,
                 f"Личные вещи (одежда/сумка) находятся на кассовом столе {t0:.1f}-{t1:.1f} с "
                 f"({t1 - t0:.0f} с). Личные вещи должны храниться вне кассового узла.")


rule("R7", "streak", T_R7, NPA_R7, True, _r7_trig, _r7_eval)


# ---------- R8 Порядок рабочего места (признак) -----------------------------------

def _r8_trig(ft, cfg):
    out = [("drink", t, None) for t in ft.event_times("drink")]
    for state, label in (("stamp_on_desk", "Именные штампы остаются на столе при уходе кассира"),
                         ("screen_open", "Рабочий экран остаётся открытым при уходе кассира")):
        m = ft.mask_and(ft.mask(state), ft.mask("cashier_away"))
        for t0, t1 in ft.streaks_from_mask(m, cfg.r8_min):
            out.append((label, t0, (t0, t1)))
    return out


def _r8_eval(ft, anchor, cfg):
    label, t, run = anchor
    tail = f"({t:.1f}-{run[1]:.1f} с)" if run else f"({t:.1f} с)"
    frames = _streak_frames(ft, *run) if run else [round(t, 1), round(min(t + 0.5, ft.duration), 1)]
    return Event("R8", T_R8, t, frames, None, False,
                 f"{label} {tail}. Прямого запрета в открытых актах РК нет — признак для проверки.")


rule("R8", "order", T_R8, None, False, _r8_trig, _r8_eval)


# ---------- R9 Дверь и посторонние ------------------------------------------------

def _r9_trig(ft, cfg):
    runs = ft.streaks("door_open", cfg.r9_min)
    enters = [t for t in ft.event_times("person_enter") if ft.state_at("door_open", t)]
    anchors, used = [], set()
    for a, b in runs:
        inner = next((t for t in enters if a <= t <= b), None)
        if inner is not None:
            used.add(inner)
        anchors.append((a, (a, b), inner))
    for t in enters:
        if t not in used:
            anchors.append((t, None, t))
    return anchors


def _r9_eval(ft, anchor, cfg):
    t0, run, inner = anchor
    if run and inner:
        desc = (f"Дверь кассовой зоны открыта ({run[0]:.1f}-{run[1]:.1f} с), на {inner:.1f} с "
                f"в кассовый узел входит посторонний.")
        frames = _streak_frames(ft, *run) + [round(min(inner + 0.5, ft.duration), 1)]
        tc = inner
    elif run:
        desc = f"Дверь кассовой зоны остаётся открытой {run[0]:.1f}-{run[1]:.1f} с."
        frames = _streak_frames(ft, *run)
        tc = run[0]
    else:
        desc = f"На {t0:.1f} с в кассовую зону входит посторонний при открытой двери."
        frames = [round(t0, 1), round(min(t0 + 0.5, ft.duration), 1)]
        tc = t0
    return Event("R9", T_R9, tc, frames[:3], NPA_R9, True, desc)


rule("R9", "order", T_R9, NPA_R9, True, _r9_trig, _r9_eval)


# ---------- R10 Приём без пересчёта и оформления -----------------------------------

def _r10_trig(ft, cfg):
    return [(t, t) for t in ft.event_times("money_to_safe")]


def _r10_eval(ft, anchor, cfg):
    t2 = anchor[0]
    h = ft.last_event("money_handover", t2 - cfg.r10_back, t2)
    if h is None:
        return None  # укладка без приёма от клиента в кадре — норма (взял из сейфа)
    if ft.any_event("count_start", h, t2) or ft.any_event("data_entry", h, t2):
        return None
    return Event("R10", T_R10, t2, [round(h, 1), round(t2, 1)], NPA_R10, True,
                 f"Деньги, принятые на {h:.1f} с, помещаются в сейф на {t2:.1f} с без "
                 f"зафиксированного полистного пересчёта и оформления операции.")


rule("R10", "order", T_R10, NPA_R10, True, _r10_trig, _r10_eval)


# ---------- R11 Деньги прошлого клиента при новом клиенте --------------------------
# Х-4/Х-47: кассир не убрала деньги первого клиента (в сейф), приняла второго
# и смешала стопки. Видимый факт — банкноты на столе в момент старта новой
# сессии; квалификация — хранение в закрывающемся устройстве (п. 20 абз. 2).

def _r11_trig(ft, cfg):
    anchors = [(s.t0, s.t0) for s in ft.sessions()[1:]]
    anchors += [(t, t) for t in ft.event_times("person_enter")]
    return sorted(anchors)


def _r11_eval(ft, anchor, cfg):
    t0 = anchor[0]
    # новый клиент приходит при открытой сессии и «висящих» деньгах
    cp = ft.states.get("client_present")
    if cp is not None and not cp[ft.tick_index(t0)]:
        return None
    m = ft.mask_or("banknotes_on_desk", "money_bag_on_desk")
    i0 = ft.tick_index(max(0.0, t0 - 1.0))
    i1 = ft.tick_index(min(t0 + cfg.r11_grace, ft.duration))
    if not any(m[i] for i in range(i0, i1 + 1)):
        return None
    # кластеризация: повторные person_enter при тех же деньгах — один эпизод;
    # сохраняем первый и последний якорь кластера (начало и конец эпизода)
    cand = sorted(t for t in ft.event_times("person_enter")
                  if cp is None or cp[ft.tick_index(t)])
    clusters: list[list[float]] = []
    for t in cand:
        if clusters and t - clusters[-1][-1] <= cfg.r11_gap:
            clusters[-1].append(t)
        else:
            clusters.append([t])
    keep = {c[0] for c in clusters} | {c[-1] for c in clusters}
    if cand and t0 in cand and t0 not in keep:
        return None  # дубль внутри кластера
    h = ft.last_event("money_handover", 0.0, t0 - cfg.r11_stale)
    if h is None and t0 > 0:
        return None  # деньги на столе не от предыдущего клиента
    htxt = f", принятые на {h:.1f} с" if h is not None else ""
    return Event("R11", T_R11, t0, [round(max(0.0, t0 - 1.0), 1), round(min(t0 + 1.0, ft.duration), 1)],
                 NPA_R2, True,
                 f"На {t0:.1f} с появляется новый человек, а банкноты на рабочей поверхности"
                 f"{htxt} не убраны на хранение: приём и хранение наличных не разделены, "
                 f"возможно смешивание сумм разных клиентов.")


rule("R11", "order", T_R11, NPA_R2, True, _r11_trig, _r11_eval)