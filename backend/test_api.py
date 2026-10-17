import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import main


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"API_KEY": "test-key"})
        self.env.start()
        self.addCleanup(self.env.stop)
        main.jobs.clear()
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)
        self.headers = {"X-API-Key": "test-key"}

    def upload(self, name="video.mov", content=b"test video"):
        return self.client.post(
            "/api/v1/analyze",
            headers=self.headers,
            files={"file": (name, content, "video/quicktime")},
        )

    def test_auth(self):
        for method, url in [("POST", "/api/v1/analyze"), ("GET", "/api/v1/jobs/missing")]:
            for headers in [{}, {"X-API-Key": "wrong"}]:
                self.assertEqual(self.client.request(method, url, headers=headers).status_code, 401)
        with patch.dict(os.environ, {"API_KEY": ""}):
            self.assertEqual(self.upload().status_code, 503)

    def test_upload_and_job(self):
        response = self.upload("VIDEO.MOV")
        self.assertEqual(response.status_code, 202)
        job_id = response.json()["job_id"]
        response = self.client.get(f"/api/v1/jobs/{job_id}", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "job_id": job_id,
            "status": "failed",
            "error": "Analysis model is not configured",
        })
        self.assertEqual(self.upload("video.mp4").status_code, 202)
        self.assertEqual(self.client.get("/api/v1/jobs/missing", headers=self.headers).status_code, 404)

    def test_invalid_upload(self):
        self.assertEqual(self.upload("video.mov.exe").status_code, 415)
        self.assertEqual(self.upload(content=b"").status_code, 400)
        with patch.object(main, "MAX_FILE_SIZE", 4):
            self.assertEqual(self.upload(content=b"12345").status_code, 413)
            self.assertEqual(self.upload(content=b"1234").status_code, 202)
        self.assertEqual(self.client.post("/api/v1/analyze", headers=self.headers).status_code, 422)


if __name__ == "__main__":
    unittest.main()
