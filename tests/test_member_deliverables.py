import csv
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.deliverables import DATASET, trufor_results
from backend.app.main import app


class DeliveryTests(unittest.TestCase):
    def test_dataset_integrity(self):
        with (DATASET / "sample_manifest.csv").open(encoding="utf-8-sig") as file:
            rows = list(csv.DictReader(file))
        self.assertEqual(len(rows), 200)
        pairs = {}
        for row in rows:
            path = DATASET / row["relative_path"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), row["sha256"])
            with Image.open(path) as image:
                self.assertEqual(image.size, (int(row["width"]), int(row["height"])))
                image.verify()
            pairs.setdefault(row["pair_id"], []).append(row)
        self.assertEqual(len(pairs), 100)
        for rows in pairs.values():
            self.assertEqual(len(rows), 2)
            self.assertEqual({r["class_id"] for r in rows}, {"0", "1"})
            self.assertEqual(len({r["split"] for r in rows}), 1)

    def test_simulated_threshold_counts(self):
        self.assertEqual(trufor_results(0.65)["false_positive_rate"], 0)
        self.assertEqual(trufor_results(0.65)["true_positive_rate"], 1)
        self.assertEqual(trufor_results(0.70)["true_positive_rate"], 0.5)

    def test_real_exif_and_path_boundary(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(settings, "data_dir", directory):
            from io import BytesIO
            image = Image.new("RGB", (16, 16), "white")
            exif = Image.Exif()
            exif[271] = "IntegrationTestCamera"
            buffer = BytesIO()
            image.save(buffer, format="JPEG", exif=exif)
            with TestClient(app) as client:
                upload = client.post("/api/v1/upload", files={"files": ("test.jpg", buffer.getvalue(), "image/jpeg")})
                ref = upload.json()["uploaded"][0]["media_ref"]
                payload = {"tool": "source_trace", "request_id": "test_exif", "payload": {
                    "files": [{"kind": "image", "ref": ref}], "signals": {"c2pa_status": "valid"}}}
                result = client.post("/api/v1/tools/source_trace", json=payload).json()
                self.assertEqual(result["status"], "success")
                # C2PA 现在做「清单存在性检测」：普通 PIL 生成的 JPEG 无 C2PA 标记 → absent
                self.assertEqual(result["evidence"]["c2pa"]["status"], "absent")
                self.assertIn("存在性检测", result["evidence"]["c2pa"]["detail"])
                self.assertIn("IntegrationTestCamera", str(result["evidence"]["exif"]))
                from backend.app.agent.fuser import fuser
                layer = fuser.fuse("test", {"source_trace": result["evidence"]}, creator_submission={"original_file": [ref]})
                self.assertIsNone(layer.creator_submission.credential)
                payload["payload"]["files"][0]["ref"] = "uploads/../../outside.jpg"
                response = client.post("/api/v1/tools/source_trace", json=payload)
                self.assertEqual(response.status_code, 500)
                self.assertEqual(response.json()["detail"]["message"], "Invalid uploaded media reference")


if __name__ == "__main__":
    unittest.main()
