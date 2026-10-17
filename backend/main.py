import os
from pathlib import Path
from secrets import compare_digest
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, UploadFile

MAX_FILE_SIZE = 200 * 1024 * 1024
# ponytail: jobs live in one process and reset on restart; add storage with real analysis.
jobs: dict[str, dict] = {}


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
        # No model yet: report failure instead of inventing an analysis result.
        jobs[job_id] = {
            "job_id": job_id,
            "status": "failed",
            "error": "Analysis model is not configured",
        }
        return {"job_id": job_id}
    finally:
        await file.close()


@app.get("/api/v1/jobs/{job_id}")
def get_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    return jobs[job_id]
