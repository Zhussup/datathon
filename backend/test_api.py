import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import main
from fastapi.testclient import TestClient

import worker

ROOT = Path(main.__file__).resolve().parent.parent


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"API_KEY": "test-key"})
        self.env.start()
        self.addCleanup(self.env.stop)
        worker.store.clear()
        self.addCleanup(worker.store.clear)
        storage = Path(tempfile.mkdtemp(prefix="forte-testing-"))
        self.addCleanup(shutil.rmtree, storage, ignore_errors=True)
        storage_patch = patch.object(main, "STORAGE_DIR", storage)
        storage_patch.start()
        self.addCleanup(storage_patch.stop)
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)
        self.headers = {"X-API-Key": "test-key"}

    def upload(self, name="video.mov", content=b"test video bytes"):
        return self.client.post(
            "/api/v1/analyze",
            headers=self.headers,
            files={"file": (name, content, "video/quicktime")},
        )

    def wait_job(self, job_id, timeout=15):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            data = self.client.get(f"/api/v1/jobs/{job_id}", headers=self.headers).json()
            if data["status"] != "processing":
                return data
            time.sleep(0.05)
        self.fail("job did not finish in time")

    def test_auth(self):
        for method, url in [("POST", "/api/v1/analyze"), ("GET", "/api/v1/jobs/missing")]:
            for headers in [{}, {"X-API-Key": "wrong"}]:
                self.assertEqual(self.client.request(method, url, headers=headers).status_code, 401)
        with patch.dict(os.environ, {"API_KEY": ""}):
            self.assertEqual(self.upload().status_code, 503)

    def test_upload_and_job(self):
        # Перцепция не готова (W2/W3): задание честно падает в failed, без выдумок.
        response = self.upload("VIDEO.MOV")
        self.assertEqual(response.status_code, 202)
        job_id = response.json()["job_id"]
        data = self.wait_job(job_id)
        self.assertEqual(data["status"], "failed")
        self.assertIn("configured", data["error"])
        self.assertEqual(self.upload("video.mp4").status_code, 202)
        self.assertEqual(self.client.get("/api/v1/jobs/missing", headers=self.headers).status_code, 404)

    def test_demo_cycle_violation(self):
        # Х-15: мешок на столе + кассир отходит -> R2 @15. Кадры не вырезаются
        # (в тесте байты не видео), поле evidence_frames остаётся пустым.
        fixture = str(ROOT / "fixtures" / "X-15.json")
        with patch.dict(os.environ, {"PIPELINE_DEMO_FACTS": fixture}):
            job_id = self.upload().json()["job_id"]
            data = self.wait_job(job_id)
        self.assertEqual(data["status"], "done")
        self.assertEqual(data["verdict"], "violation")
        self.assertEqual(len(data["violations"]), 1)
        v = data["violations"][0]
        for key in ("type", "timecode_sec", "description", "evidence_frames", "npa", "rule_id"):
            self.assertIn(key, v)
        self.assertEqual(v["rule_id"], "R2")
        self.assertEqual(v["timecode_sec"], 15.0)
        self.assertEqual(v["type"], "Безнадзорные ценности")
        self.assertTrue(isinstance(v["npa"], str) and v["npa"])
        self.assertEqual(v["evidence_frames"], [])

    def test_demo_cycle_clean(self):
        fixture = str(ROOT / "fixtures" / "X-3.json")
        with patch.dict(os.environ, {"PIPELINE_DEMO_FACTS": fixture}):
            job_id = self.upload().json()["job_id"]
            data = self.wait_job(job_id)
        self.assertEqual(data, {
            "job_id": job_id,
            "status": "done",
            "verdict": "no_violation",
            "violations": [],
        })

    def test_demo_bad_fixture(self):
        with patch.dict(os.environ, {"PIPELINE_DEMO_FACTS": "/no/such/fixture.json"}):
            job_id = self.upload().json()["job_id"]
            data = self.wait_job(job_id)
        self.assertEqual(data["status"], "failed")
        self.assertIn("не найден", data["error"])

    def test_invalid_upload(self):
        self.assertEqual(self.upload("video.mov.exe").status_code, 415)
        self.assertEqual(self.upload(content=b"").status_code, 400)
        with patch.object(main, "MAX_FILE_SIZE", 4):
            self.assertEqual(self.upload(content=b"12345").status_code, 413)
            self.assertEqual(self.upload(content=b"1234").status_code, 202)
        self.assertEqual(self.client.post("/api/v1/analyze", headers=self.headers).status_code, 422)


if __name__ == "__main__":
    unittest.main()