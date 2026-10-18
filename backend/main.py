import os
from datetime import datetime, timezone
from pathlib import Path
from secrets import compare_digest
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

import worker
from pipeline import rules as pipeline_rules
from pipeline.rules import RULES
from worker import store  # noqa: F401 — tests import this to clear job state

MAX_FILE_SIZE = 200 * 1024 * 1024
# ponytail: one dir per upload, keep files for manual inspection; add cleanup when it grows.
STORAGE_DIR = Path(os.environ.get("STORAGE_DIR", Path(__file__).parent / "storage"))

worker.start_background()


def check_api_key(x_api_key: Annotated[str | None, Header()] = None):
    expected = os.environ.get("API_KEY", "")
    if not expected:
        raise HTTPException(503, "API_KEY is not configured")
    if not x_api_key or not compare_digest(x_api_key.encode(), expected.encode()):
        raise HTTPException(401, "Invalid API key")


# Ключ проверяется на каждом API-ручнике (Depends), НЕ на app целиком:
# статика фронтенда должна отдаваться без ключа — жюри открывает URL в браузере.
app = FastAPI(title="Forte Vision API")

# Фронт может лежать на другом порту/хосте; ключ всё равно проверяет заголовок.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key"],
)


@app.post("/api/v1/analyze", status_code=202, dependencies=[Depends(check_api_key)])
async def analyze(file: UploadFile):
    try:
        if Path(file.filename or "").suffix.lower() not in {".mov", ".mp4"}:
            raise HTTPException(415, "Expected a MOV or MP4 file")
        if not file.size:
            raise HTTPException(400, "File is empty")
        if file.size > MAX_FILE_SIZE:
            raise HTTPException(413, "File exceeds 200 MB")
        # ISO BMFF: 4 байта BE-длины первого атома + 4 байта тип; «ftyp» всегда на offset 4.
        # Литеральная проверка первых 4 байт отвергла бы ВСЕ реальные .mov из open/videos/
        # (там \x00\x00\x00\x14ftypqt  ...). После read обязателен seek(0), иначе цикл
        # записи ниже потеряет первые 8 байт.
        head = await file.read(8)
        await file.seek(0)
        if len(head) < 8 or head[4:8] != b"ftyp":
            raise HTTPException(415, "Не похоже на MOV/MP4: отсутствует атом ftyp")

        job_id = uuid4().hex
        dest = STORAGE_DIR / job_id / "video.mov"
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            with dest.open("wb") as out:
                while (chunk := await file.read(1 << 20)):
                    out.write(chunk)
        except OSError:
            raise HTTPException(500, "Could not store uploaded file")
        worker.submit(job_id, dest)
        return {"job_id": job_id}
    finally:
        await file.close()


@app.get("/api/v1/jobs/{job_id}", dependencies=[Depends(check_api_key)])
def get_job(job_id: str):
    job = store.public(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return job


@app.get("/api/v1/version", dependencies=[Depends(check_api_key)])
def version():
    """Снимок сборки для жюри и приёмки: сколько правил, какой бюджет обработки."""
    mtime = Path(pipeline_rules.__file__).stat().st_mtime
    return {
        "service": "forte-vision",
        "engine": "pipeline.engine",
        "rules_count": len(RULES),
        "rules_version": datetime.fromtimestamp(mtime, timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "process_budget_sec": worker.PROCESS_BUDGET_SEC,
        "worker_count": worker.WORKER_COUNT,
    }


# ---------- статика фронтенда (тот же origin, что и API) ----------
# Жюри открывает URL в браузере → index.html + assets; API-роуты выше имеют
# приоритет (регистрируются раньше), всё остальное уходит в dist.
# dist собирается с VITE_API_KEY → ключ уже запечён, UI работает сразу.
_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if (_DIST / "index.html").exists():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="frontend")