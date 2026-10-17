"""Перцепция: видео -> таблица фактов.

Сейчас это заглушка: детектор (W2) и трекер со эвристиками состояний (W3) впереди.
По умолчанию выбрасывается PerceptionUnavailable — задание честно падает в failed,
никаких вымышленных вердиктов. PIPELINE_DEMO_FACTS=<fixtures/*.json> подаёт
рукописную таблицу фактов в движок — режим сквозной проверки API и UI, для жюри
его включать нельзя.

Контракт для будущей реализации: extract_facts(video_path, deadline) -> FactTable,
где deadline — monotonic-метка крайнего времени (FAQ 14: ≤5 минут на видео);
при истечении бюджета реализация должна бросать worker.ProcessingTimeout.
"""
import os
import sys
from pathlib import Path


class PerceptionUnavailable(RuntimeError):
    """Перцепция не готова обработать это видео."""


DEMO_ENV = "PIPELINE_DEMO_FACTS"

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def extract_facts(video_path: Path, deadline: float | None = None):
    demo = os.environ.get(DEMO_ENV)
    if not demo:
        raise PerceptionUnavailable(
            f"детектор не подключен (W2/W3 в процессе); для сквозного демо задайте "
            f"{DEMO_ENV}=путь/к/fixtures/*.json")
    path = Path(demo)
    if not path.exists():
        raise PerceptionUnavailable(f"{DEMO_ENV}: файл не найден: {demo}")
    from pipeline.facts import FactTable
    return FactTable.from_spec(str(path))