import os
from copy import deepcopy
from uuid import uuid4

import requests

from api.mock_api import get_mock_response, get_mock_review_response
from backend.demo.cases import CASE_A, CASE_B

USE_MOCK = os.getenv("BEAUTYPROOF_USE_MOCK", "false").lower() != "false"
API_BASE_URL = os.getenv("BEAUTYPROOF_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
# 与后端 BEAUTYPROOF_API_KEY 保持一致；留空表示后端未开启鉴权
API_KEY = os.getenv("BEAUTYPROOF_API_KEY", "").strip()


def auth_headers(extra: dict | None = None) -> dict:
    """构造请求头：后端开启鉴权时自动附带 X-API-Key。"""
    headers = {"X-API-Key": API_KEY} if API_KEY else {}
    if extra:
        headers.update(extra)
    return headers


def api_get(path: str, **kwargs):
    """统一的 GET 入口（自动拼接 base url 并带鉴权头）。"""
    kwargs["headers"] = {**auth_headers(), **kwargs.pop("headers", {})}
    kwargs.setdefault("timeout", 30)
    return requests.get(f"{API_BASE_URL}{path}", **kwargs)


def api_post(path: str, **kwargs):
    """统一的 POST 入口（自动拼接 base url 并带鉴权头）。"""
    kwargs["headers"] = {**auth_headers(), **kwargs.pop("headers", {})}
    kwargs.setdefault("timeout", 120)
    return requests.post(f"{API_BASE_URL}{path}", **kwargs)


def _result(response):
    response.raise_for_status()
    envelope = response.json()
    if envelope.get("status") != "success":
        error = envelope.get("error") or {}
        raise ValueError(error.get("message", "Main Agent request failed"))
    return envelope["result"]


def _upload(file):
    response = api_post(
        "/api/v1/upload",
        files={"files": (file.name, file.getvalue(), file.type)},
        timeout=60,
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
    return _result(api_post("/api/v1/verify", json=payload, timeout=120))


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
    return _result(api_post("/api/v1/creators/review", json=payload, timeout=600))
