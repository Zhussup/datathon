import os
from pathlib import Path
from secrets import compare_digest
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, UploadFile

import worker
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


app = FastAPI(title="Forte Vision API", dependencies=[Depends(check_api_key)])


@app.post("/api/v1/analyze", status_code=202)
async def analyze(file: UploadFile):
    try:
        if Path(file.filename or "").suffix.lower() not in {".mov", ".mp4"}:
            raise HTTPException(415, "Expected a MOV or MP4 file")
        if not file.size:
            raise HTTPException(400, "File is empty")
        if file.size > MAX_FILE_SIZE:
            raise HTTPException(413, "File exceeds 200 MB")

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


@app.get("/api/v1/jobs/{job_id}")
def get_job(job_id: str):
    job = store.public(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return job