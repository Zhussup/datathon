"""Воркер обработки видео: очередь -> перцепция -> движок -> ответ раздела 10 ТЗ.

- Потоков-воркеров WORKER_COUNT (по умолчанию 1; на жюрейском прогоне поднять,
  чтобы очередь не съела лимит 5 минут на каждое видео).
- Бюджет PROCESS_BUDGET_SEC (по умолчанию 270 с — запас до лимита FAQ 14);
  при истечении задание честно падает в failed, частичный вердикт не выдаём.
- Кадры-доказательства добираются из сохранённого видео через OpenCV; если
  opencv не установлен (лёгкое dev-окружение) обработка проходит, а
  evidence_frames остаётся пустым — описание несёт смысл и без кадров.
"""
import base64
import os
import queue
import sys
import threading
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline.engine import run_engine  # noqa: E402
from perception import extract_facts, PerceptionUnavailable  # noqa: E402

PROCESS_BUDGET_SEC = float(os.environ.get("PROCESS_BUDGET_SEC", "270"))
WORKER_COUNT = max(1, int(os.environ.get("WORKER_COUNT", "1")))

_API_KEYS = ("type", "timecode_sec", "description", "npa", "rule_id")


class ProcessingTimeout(RuntimeError):
    pass


def _check_deadline(deadline: float | None) -> None:
    if deadline is not None and time.monotonic() >= deadline:
        raise ProcessingTimeout(f"обработка превысила лимит {PROCESS_BUDGET_SEC:.0f} c")


class JobStore:
    def __init__(self) -> None:
        self.jobs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def create(self, job_id: str, video_path: Path) -> None:
        with self._lock:
            self.jobs[job_id] = {
                "job_id": job_id,
                "status": "processing",
                "video_path": str(video_path),
                "result": None,
                "error": None,
            }

    def finish(self, job_id: str, result: dict) -> None:
        with self._lock:
            job = self.jobs[job_id]
            job["status"] = "done"
            job["result"] = result

    def fail(self, job_id: str, error: str) -> None:
        with self._lock:
            job = self.jobs.get(job_id)
            if job is not None:
                job["status"] = "failed"
                job["error"] = error

    def public(self, job_id: str) -> dict | None:
        with self._lock:
            job = self.jobs.get(job_id)
            if job is None:
                return None
            pub = {"job_id": job["job_id"], "status": job["status"]}
            if job["status"] == "done":
                pub.update(job["result"])
            if job["status"] == "failed":
                pub["error"] = job["error"]
            return pub

    def clear(self) -> None:
        with self._lock:
            self.jobs.clear()


store = JobStore()
_tasks: queue.Queue[str] = queue.Queue()
_started = False
_start_lock = threading.Lock()


def extract_frame_jpegs(video_path: Path | None, timestamps, deadline: float | None) -> dict[float, str]:
    """timestamp_sec -> JPEG base64. Без opencv или нечитаемого видео -> {}."""
    if not video_path:
        return {}
    try:
        import cv2
    except ImportError:
        return {}
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return {}
    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    out: dict[float, str] = {}
    for ts in sorted(set(timestamps)):
        try:
            _check_deadline(deadline)
        except ProcessingTimeout:
            break
        if fps and total:
            n = max(0, min(int(round(ts * fps)), total - 1))
            cap.set(cv2.CAP_PROP_POS_FRAMES, n)
        ok, frame = cap.read()
        if ok:
            ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            if ok:
                out[round(ts, 1)] = base64.b64encode(buf.tobytes()).decode("ascii")
    cap.release()
    return out


def assemble(facts, video_path: Path | None, deadline: float | None = None) -> dict:
    """Движок + кадры -> dict вида done-ответа API (без job_id/status — их ставит store)."""
    engine = run_engine(facts)
    wanted = sorted({f["timestamp_sec"] for v in engine["violations"] for f in v["evidence_frames"]})
    jpegs = extract_frame_jpegs(video_path, wanted, deadline)
    violations = []
    for v in engine["violations"]:
        item = {k: v[k] for k in _API_KEYS}
        item["evidence_frames"] = [
            {"timestamp_sec": f["timestamp_sec"], "image_base64": jpegs.get(f["timestamp_sec"], "")}
            for f in v["evidence_frames"]
        ]
        # кадры, которые не удалось вырезать, не выдаём; остальное несёт описание
        item["evidence_frames"] = [f for f in item["evidence_frames"] if f["image_base64"]]
        violations.append(item)
    return {"verdict": engine["verdict"], "violations": violations}


def process_video(video_path: Path, deadline: float | None) -> dict:
    _check_deadline(deadline)
    facts = extract_facts(video_path, deadline)
    _check_deadline(deadline)
    return assemble(facts, video_path, deadline)


def _run(job: dict) -> None:
    deadline = time.monotonic() + PROCESS_BUDGET_SEC
    try:
        result = process_video(Path(job["video_path"]), deadline)
        if time.monotonic() >= deadline:
            store.fail(job["job_id"], "обработка превысила лимит времени")
            return
        store.finish(job["job_id"], result)
    except ProcessingTimeout as e:
        store.fail(job["job_id"], str(e))
    except PerceptionUnavailable as e:
        store.fail(job["job_id"], f"Perception is not configured: {e}")
    except Exception as e:  # воркер не должен умирать тихо
        store.fail(job["job_id"], f"Processing error: {type(e).__name__}: {e}")


def submit(job_id: str, video_path: Path) -> None:
    store.create(job_id, video_path)
    _tasks.put(job_id)


def start_background() -> None:
    global _started
    with _start_lock:
        if _started:
            return
        for _ in range(WORKER_COUNT):
            threading.Thread(target=_loop, name="forte-worker", daemon=True).start()
        _started = True


def _loop() -> None:
    while True:
        job_id = _tasks.get()
        try:
            job = store.jobs.get(job_id)
            if job is not None:
                _run(job)
        finally:
            _tasks.task_done()