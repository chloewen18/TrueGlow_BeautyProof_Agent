import os
from copy import deepcopy
from uuid import uuid4

import requests

from api.mock_api import get_mock_response, get_mock_review_response
from backend.demo.cases import CASE_A, CASE_B

USE_MOCK = os.getenv("BEAUTYPROOF_USE_MOCK", "false").lower() != "false"
API_BASE_URL = os.getenv("BEAUTYPROOF_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def _result(response):
    response.raise_for_status()
    envelope = response.json()
    if envelope.get("status") != "success":
        error = envelope.get("error") or {}
        raise ValueError(error.get("message", "Main Agent request failed"))
    return envelope["result"]


def _upload(file):
    response = requests.post(
        f"{API_BASE_URL}/api/v1/upload",
        files={"files": (file.name, file.getvalue(), file.type)}, timeout=60,
    )
    response.raise_for_status()
    media = response.json()["uploaded"][0]
    return {"kind": media["kind"], "ref": media["media_ref"]}


def analyze_content(uploaded_file, text, product_name="", user_need="", case_id="case_b"):
    if USE_MOCK:
        return get_mock_response(case_id)
    payload = deepcopy(CASE_A if case_id == "case_a" else CASE_B)
    payload["content_id"] = f"content_{uuid4().hex[:12]}"
    payload["content"].update(
        body_text=text, title=text[:80], product=product_name, media=[_upload(uploaded_file)]
    )
    payload["user_context"] = {"concerns": user_need, "goal": "核验可信度"}
    return _result(requests.post(f"{API_BASE_URL}/api/v1/verify", json=payload, timeout=120))


def submit_creator_evidence(content_id, original_request_id, original_file, filter_info=""):
    if USE_MOCK:
        return get_mock_review_response()
    payload = {
        "content_id": content_id, "original_request_id": original_request_id,
        "creator_submission": {
            "original_file": [_upload(original_file)],
            "shooting_params": {"description": filter_info},
        },
    }
    return _result(requests.post(f"{API_BASE_URL}/api/v1/creators/review", json=payload, timeout=120))
