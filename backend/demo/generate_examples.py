"""生成三份完整、可直接被前端 Mock 接入的示例 JSON（冻结信封，见 API_SPEC §6）。

通过真实 FastAPI 端点（TestClient）跑通，确保响应结构与联调时完全一致：
  examples/case_a_response.json       Case A：真实但缺来源 → insufficient_evidence
  examples/case_b_response.json       Case B：磨皮+曝光变化 → high_risk_misleading
  examples/case_c_review_response.json Case C：创作者补证复核 → 结论更新 + 可信妆效凭证

用法：
  cd backend
  ../.venv/bin/python demo/generate_examples.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

# 用临时 data_dir，避免污染仓库真实证据库
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="beautyproof_examples_")

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent
REPO = BACKEND.parent
EXAMPLES = REPO / "examples"
EXAMPLES.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(HERE))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from cases import CASE_A, CASE_B, CASE_C_SUBMISSION  # noqa: E402


def _write(name: str, payload: dict) -> None:
    path = EXAMPLES / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  -> {path.relative_to(REPO)}  ({len(json.dumps(payload, ensure_ascii=False))} bytes)")


def main() -> None:
    client = TestClient(app)

    print("[1/3] Case A /verify")
    r_a = client.post("/api/v1/verify", json=CASE_A)
    assert r_a.status_code == 200, r_a.text
    _write("case_a_response.json", r_a.json())

    print("[2/3] Case B /verify")
    r_b = client.post("/api/v1/verify", json=CASE_B)
    assert r_b.status_code == 200, r_b.text
    case_b = r_b.json()
    _write("case_b_response.json", case_b)
    original_rid = case_b["request_id"]
    print(f"      original_request_id = {original_rid}, verdict = {case_b['result']['verdict']}")

    print("[3/3] Case C /creators/review")
    review_payload = dict(CASE_C_SUBMISSION)
    review_payload["original_request_id"] = original_rid
    r_c = client.post("/api/v1/creators/review", json=review_payload)
    assert r_c.status_code == 200, r_c.text
    case_c = r_c.json()
    _write("case_c_review_response.json", case_c)
    print(f"      before = {case_c['result']['before_verdict']} -> after = {case_c['result']['after_verdict']}")

    print("\nDone. Examples written to examples/")


if __name__ == "__main__":
    main()
