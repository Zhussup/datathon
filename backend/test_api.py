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
        # Валидный ISO BMFF-заголовок: BE-длина 0x14 + «ftyp» + «qt  » — main.py проверяет
        # именно bytes[4:8] == b"ftyp", иначе отвергнет как 415. Старые «test video bytes»
        # теперь не проходят сигнатуру, и это правильно.
        self.mov_header = b"\x00\x00\x00\x14ftypqt  "

    def upload(self, name="video.mov", content=None):
        if content is None:
            content = self.mov_header + b"\x00" * 24
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
        with patch.object(main, "MAX_FILE_SIZE", 32):
            # 64 байта (заголовок + 56 байт хвоста) — превышает лимит.
            self.assertEqual(self.upload(content=self.mov_header + b"X" * 56).status_code, 413)
            # 24 байта (заголовок + 16 байт хвоста) — проходит лимит, не сигнатуру.
            self.assertEqual(self.upload(content=self.mov_header + b"\x00" * 16).status_code, 202)
        self.assertEqual(self.client.post("/api/v1/analyze", headers=self.headers).status_code, 422)

    def test_version_auth(self):
        # /version защищён тем же X-API-Key, что и остальные маршруты.
        self.assertEqual(self.client.get("/api/v1/version").status_code, 401)
        self.assertEqual(
            self.client.get("/api/v1/version", headers={"X-API-Key": "wrong"}).status_code, 401
        )
        with patch.dict(os.environ, {"API_KEY": ""}):
            self.assertEqual(self.client.get("/api/v1/version", headers=self.headers).status_code, 503)

    def test_version_payload(self):
        data = self.client.get("/api/v1/version", headers=self.headers).json()
        self.assertEqual(data["service"], "forte-vision")
        self.assertEqual(data["engine"], "pipeline.engine")
        self.assertEqual(data["rules_count"], 10)
        # ISO-дата в UTC: 2026-10-17T...Z, длина 20.
        self.assertEqual(len(data["rules_version"]), 20)
        self.assertTrue(data["rules_version"].endswith("Z"))
        self.assertGreaterEqual(data["process_budget_sec"], 270)
        self.assertGreaterEqual(data["worker_count"], 1)

    def test_upload_signature_reject(self):
        # .mov с правильным расширением, но без атома ftyp на offset 4.
        response = self.upload(content=b"X" * 16)
        self.assertEqual(response.status_code, 415)
        self.assertIn("ftyp", response.json()["detail"])

    def test_upload_signature_short_file(self):
        # 1–7 байт: атома ftyp физически нет.
        response = self.upload(content=b"abc")
        self.assertEqual(response.status_code, 415)
        self.assertIn("ftyp", response.json()["detail"])

    def test_upload_signature_real_mov(self):
        # Реальный заголовок из open/videos/Х-30.mov: BE-длина 0x14 + "ftyp" + "qt  ".
        head = b"\x00\x00\x00\x14ftypqt  " + b"\x00" * 24
        self.assertEqual(self.upload(content=head).status_code, 202)


if __name__ == "__main__":
    unittest.main()