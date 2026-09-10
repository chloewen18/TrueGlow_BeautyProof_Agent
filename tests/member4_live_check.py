import requests
from backend.app.integrations.member4.service import evidence_db

base = "http://127.0.0.1:8000/api/v1"
product = next(p["product_name"] for p in evidence_db()["products"] if "True Match" in p["product_name"])
response = requests.post(base + "/member4/analyze", json={"text":"中等遮瑕，很服帖", "product":product}, timeout=60)
response.raise_for_status()
assert any(c["evidence_supported"] for c in response.json()["claims"])
response = requests.post(base + "/verify", json={"content_id":"member4_live_check",
    "content":{"body_text":"中等遮瑕，很服帖", "product":product}}, timeout=60)
response.raise_for_status()
envelope = response.json()
assert envelope["status"] == "success", envelope
raw = envelope["result"]["report"]["evidence"]["text_evidence"]["raw"]
assert raw["member4_analysis"]["claims"]
print("PASS: live text analysis, exact product evidence, Main Agent report")
