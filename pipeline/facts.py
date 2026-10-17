"""Таблица фактов — единственный язык между перцепцией и деревом правил.

Перцепция (детектор + трекер + эвристики состояний) наполняет таблицу по сетке
тиков (0.5 c по умолчанию): состояния-интервалы и события-моменты. Дерево правил
читает факты только через API этого модуля — окна, стрики и сессии считаются
в одном месте и калибруются как данные, а не в ветках кода правил.

Словарь состояний/событий — из rules_tree.html («Словарь примитивов»). Часть
состояний выводится в перцепции, а не здесь: например `cashier_away` — это
позиция кассирского трека относительно стола, а не инверсия `cashier_present`.
Одно и то же имя состояния обязано значить одно и то же в перцепции и в правилах.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

TICK = 0.5                 # сетка фактов, секунд
SESSION_BRIDGE_GAP = 3.0   # пауза между появлением клиента, которую ещё считаем одним визитом
SESSION_MIN_DUR = 2.0      # короче — мимолётный прохожий, не визит


@dataclass(frozen=True)
class Session:
    """Интервал визита (стрик client_present с мостом по паузам).

    open_end=True — клиент ещё в кадре в конце ролика: конец визита не наступил,
    правила «на выходе из визита» (R4) для такой сессии не спрашиваются.
    """
    t0: float
    t1: float
    open_end: bool = False


class FactTable:
    def __init__(self, video: str, duration: float, tick: float = TICK):
        if tick <= 0:
            raise ValueError("tick must be positive")
        self.video = video
        self.duration = float(duration)
        self.tick = float(tick)
        self.n = int(round(self.duration / self.tick)) + 1
        self.times = [i * self.tick for i in range(self.n)]
        self.states: dict[str, list[bool]] = {}    # имя -> по тикам
        self.events: dict[str, list[float]] = {}   # имя -> моменты
        self._sessions: list[Session] | None = None

    # ---------- сборка (перцепция / фикстуры) ----------

    @classmethod
    def from_spec(cls, path: str) -> FactTable:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        ft = cls(d["video"], d["duration"], d.get("tick", TICK))
        for name, intervals in d.get("intervals", {}).items():
            for a, b in intervals:
                ft.set_state(name, a, b)
        for name, moments in d.get("events", {}).items():
            for t in moments:
                ft.add_event(name, t)
        return ft

    def set_state(self, name: str, t0: float, t1: float, value: bool = True) -> None:
        row = self.states.setdefault(name, [False] * self.n)
        for i in range(self.tick_index(t0), self.tick_index(min(t1, self.duration)) + 1):
            row[i] = value
        self._sessions = None

    def add_event(self, name: str, t: float) -> None:
        self.events.setdefault(name, []).append(float(t))
        self._sessions = None

    # ---------- чтение (правила) ----------

    def tick_index(self, t: float) -> int:
        return max(0, min(self.n - 1, int(round(t / self.tick + 1e-9))))

    def mask(self, name: str) -> list[bool]:
        return self.states.get(name) or ([False] * self.n)

    def mask_or(self, *names: str) -> list[bool]:
        out = [False] * self.n
        for name in names:
            row = self.states.get(name)
            if row:
                for i, v in enumerate(row):
                    if v:
                        out[i] = True
        return out

    def mask_and(self, a: list[bool], b: list[bool]) -> list[bool]:
        return [va and vb for va, vb in zip(a, b)]

    def state_at(self, name: str, t: float) -> bool:
        return self.mask(name)[self.tick_index(t)]

    def event_times(self, name: str) -> list[float]:
        return sorted(self.events.get(name, []))

    def any_event(self, name: str, t0: float, t1: float) -> bool:
        return self.first_event(name, t0, t1) is not None

    def first_event(self, name: str, t0: float, t1: float) -> float | None:
        for t in self.event_times(name):
            if t0 <= t <= t1:
                return t
        return None

    def last_event(self, name: str, t0: float, t1: float) -> float | None:
        found = None
        for t in self.event_times(name):
            if t0 <= t <= t1:
                found = t
        return found

    def streaks_from_mask(self, m: list[bool], min_dur: float = 0.0) -> list[tuple[float, float]]:
        """Непрерывные отрезки True в маске: [(t0, t1), ...], t1 — исключительный край."""
        runs: list[tuple[float, float]] = []
        start: float | None = None
        end: float | None = None
        for i, v in enumerate(m):
            if v:
                if start is None:
                    start = self.times[i]
                end = self.times[i]
            elif start is not None:
                runs.append((start, end + self.tick))
                start = None
        if start is not None:
            runs.append((start, end + self.tick))
        return [(a, b) for a, b in runs if b - a >= min_dur]

    def streaks(self, name: str, min_dur: float = 0.0) -> list[tuple[float, float]]:
        return self.streaks_from_mask(self.mask(name), min_dur)

    def sessions(self) -> list[Session]:
        """Визиты: стрики client_present, паузы ≤ SESSION_BRIDGE_GAP склеиваются."""
        if self._sessions is None:
            merged: list[list[float]] = []
            for a, b in self.streaks_from_mask(self.mask("client_present"), 0.0):
                if merged and a - merged[-1][1] <= SESSION_BRIDGE_GAP:
                    merged[-1][1] = b
                else:
                    merged.append([a, b])
            out = []
            for a, b in merged:
                if b - a < SESSION_MIN_DUR:
                    continue
                out.append(Session(a, b, open_end=b >= self.duration - 1.0))
            self._sessions = out
        return self._sessions

    def active_session(self, t: float) -> Session | None:
        for s in self.sessions():
            if s.t0 <= t <= s.t1:
                return s
        return None