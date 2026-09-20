from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas.common import ToolRequest
from backend.app.tools import registry
from backend.app.integrations.visual import heat_image, pair_difference, uploaded_path
from backend.app.agent.orchestrator import main_agent
from backend.demo.cases import CASE_A, CASE_B, CASE_C_SUBMISSION

try:  # opencv 属于 requirements-models.txt，轻量（Mock）部署不安装
    import cv2  # noqa: F401
    HAS_CV2 = True
except ImportError:  # pragma: no cover
    HAS_CV2 = False


class IntegrationV2Tests(unittest.TestCase):
    def test_unknown_is_not_hard_forgery(self):
        from backend.app.agent.fuser import fuser
        from backend.app.agent.grader import grader
        result = {"integrity_score": None, "local_replacement": "Unknown", "splicing": "Unknown",
                  "inpainting": "Unknown", "reliability": "Low"}
        layer = fuser.fuse("unknown", {"image_forensics": result})
        self.assertNotEqual(grader.grade(layer).final_label.value, "high_risk_misleading")
        self.assertNotEqual(grader.grade(layer).final_label.value, "verified")

    def test_generic_retouch_is_not_lost(self):
        from backend.app.agent.fuser import fuser
        from backend.app.agent.grader import grader
        result = {"integrity_score": .9, "reliability": "Low", "per_image": [{"media_ref": "uploads/test.png",
                  "member3": {"result": {"generic_retouch": {"detected": True}, "operations": {}}}}]}
        layer = fuser.fuse("generic", {"image_forensics": result})
        self.assertTrue(any(i.finding.get("generic_retouch") == "Detected" for i in layer.visual_evidence.items))
        self.assertEqual(grader.grade(layer).final_label.value, "partially_suspicious")

    def test_missing_pair_is_unknown(self):
        response = registry.get("before_after").run(ToolRequest(tool="before_after", request_id="missing", payload={}))
        self.assertEqual(response.evidence["attribution_strength"], "Unknown")
        self.assertEqual(response.status, "partial")

    def test_invalid_real_input_not_mock(self):
        response = registry.get("image_forensics").run(ToolRequest(tool="image_forensics", request_id="bad", payload={"images":[{"ref":"../../app.py"}]}))
        self.assertEqual(response.status, "error")
        self.assertEqual(response.meta.model, "unavailable")
        with self.assertRaises(ValueError):
            uploaded_path("uploads/../../app.py")

    def test_explicit_mock_provenance(self):
        for case in [CASE_A, CASE_B]:
            result = main_agent.verify(deepcopy(case))
            self.assertIn("mock", [c["model"] for c in result["report"]["tool_calls"]])
            self.assertEqual(result["report"]["evidence"]["visual_evidence"]["raw"]["provenance"]["mode"], "mock")
        with TestClient(app) as client:
            result = client.post("/api/v1/verify", json=deepcopy(CASE_B)).json()["result"]
            payload = deepcopy(CASE_C_SUBMISSION)
            payload["original_request_id"] = result["request_id"]
            review = client.post("/api/v1/creators/review", json=payload).json()
            self.assertEqual(review["status"], "success")
            self.assertIsNone(review["result"]["credential"])

    @unittest.skipUnless(HAS_CV2, "需要 opencv（requirements-models.txt），轻量部署未安装")
    def test_zero_change_map(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "same.png"
            Image.new("RGB", (100,100), "white").save(path)
            result = pair_difference(path,path)
            self.assertEqual(result["mean_absolute_difference"], 0)
            other = Path(tmp) / "different.png"
            Image.new("RGB", (120,100), "white").save(other)
            self.assertEqual(pair_difference(path,other)["status"], "unavailable")

    def test_model_failure_does_not_become_low_score(self):
        with TestClient(app) as client:
            buffer = BytesIO()
            Image.new("RGB", (64,64), "white").save(buffer, format="PNG")
            ref = client.post("/api/v1/upload",files={"files":("test.png",buffer.getvalue(),"image/png")}).json()["uploaded"][0]["media_ref"]
            with patch("backend.app.integrations.visual.trufor", side_effect=RuntimeError("weights unavailable")), patch("backend.app.integrations.visual.single", side_effect=RuntimeError("weights unavailable")):
                result = client.post("/api/v1/verify",json={"content":{"media":[{"kind":"image","ref":ref}],"body_text":"测试"}}).json()
            self.assertEqual(result["status"], "success")
            raw = result["result"]["report"]["evidence"]["visual_evidence"]["raw"]
            self.assertIsNone(raw.get("integrity_score"))
            self.assertEqual(raw["skin_smoothing"], "Unknown")
            self.assertNotEqual(result["result"]["verdict"], "verified")
            self.assertTrue(raw["errors"])

    def test_consent_and_withdrawal(self):
        with tempfile.TemporaryDirectory() as tmp, patch("backend.app.volunteers.ROOT", Path(tmp)), TestClient(app) as client:
            buffer = BytesIO()
            Image.new("RGB", (32,32), "white").save(buffer, format="PNG")
            files = {name:(name+".png",buffer.getvalue(),"image/png") for name in ["before","after"]}
            data = {"condition":"same_conditions", "edits":"无"}
            self.assertEqual(client.post("/api/v1/volunteers/submit", data=data, files=files).status_code,422)
            receipt = client.post("/api/v1/volunteers/submit",data={**data,"consent":"true","adult_self":"true"},files=files).json()
            self.assertEqual(client.get("/api/v1/volunteers/status").json()["consented_pairs"],1)
            bad = client.post("/api/v1/volunteers/withdraw",json={"sample_id":receipt["sample_id"],"token":"bad"})
            self.assertEqual(bad.status_code,403)
            deleted = client.post("/api/v1/volunteers/withdraw",json={"sample_id":receipt["sample_id"],"token":receipt["withdrawal_token"]})
            self.assertEqual(deleted.status_code,200)
            self.assertEqual(client.get("/api/v1/volunteers/status").json()["consented_pairs"],0)


if __name__ == "__main__":
    unittest.main()
