from copy import deepcopy
from uuid import uuid4
import requests
from api.client import API_BASE_URL, _upload, _result
from backend.demo.cases import CASE_A, CASE_B, CASE_C_SUBMISSION

def verify(text, product, image=None, before=None, comments=""):
    media = [_upload(image)] if image else []
    payload = {"content_id":f"content_{uuid4().hex[:12]}", "content":{
        "body_text":text, "product":product, "media":media,
        "comments":[line for line in comments.splitlines() if line.strip()]}}
    if before and image:
        first = _upload(before)
        payload["content"]["media"].insert(0,first)
        payload["content"]["before_after"] = {"before":first,"after":media[-1]}
    return _result(requests.post(f"{API_BASE_URL}/api/v1/verify",json=payload,timeout=120))

def demo(case):
    result = _result(requests.post(f"{API_BASE_URL}/api/v1/verify",
        json=deepcopy(CASE_A if case == "A" else CASE_B),timeout=120))
    if case != "C":
        return result
    payload = deepcopy(CASE_C_SUBMISSION)
    payload["original_request_id"] = result["request_id"]
    return _result(requests.post(f"{API_BASE_URL}/api/v1/creators/review",json=payload,timeout=120))

def ocr(image):
    ref = _upload(image)
    response = requests.post(f"{API_BASE_URL}/api/v1/member4/ocr",json={"media_ref":ref["ref"]},timeout=240)
    if not response.ok:
        raise ValueError(response.json().get("detail","OCR failed"))
    return response.json()["text"]
