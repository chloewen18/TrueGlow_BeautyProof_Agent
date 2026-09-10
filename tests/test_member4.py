import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.integrations.member4.service import analyze, evidence_db, workbook_rows
from backend.app.integrations.member4.full_pipeline import evidence_matches_for_claim


class Member4Tests(unittest.TestCase):
    def test_evidence_is_product_scoped(self):
        product = "L'Oréal Paris True Match Super-Blendable Foundation"
        self.assertTrue(evidence_matches_for_claim(evidence_db(), "中等遮瑕", product))
        self.assertFalse(evidence_matches_for_claim(evidence_db(), "中等遮瑕", ""))
        self.assertFalse(evidence_matches_for_claim(evidence_db(), "中等遮瑕", "Foundation"))
        self.assertFalse(evidence_matches_for_claim(evidence_db(), "不存在", product))

    def test_negative_claim_not_supported_by_positive_brand_evidence(self):
        db = {"important_note":"test", "products":[{"product_name":"test product", "claims":[
            {"canonical_claim":"控油", "supports_claim":True}]}]}
        with patch("backend.app.integrations.member4.service.evidence_db", return_value=db):
            result = analyze("不算控油", "test product")
        claims = [c for c in result["claims"] if c["canonical_claim"] == "控油"]
        self.assertTrue(claims)
        self.assertTrue(all(not c["evidence_supported"] for c in claims))

    def test_json_and_excel_evidence_agree(self):
        excel = {(r["Product"],r["Canonical Claim"],r["Source URL"]) for r in workbook_rows("Mini功效证据表格.xlsx")}
        records = {(p["product_name"],c["canonical_claim"],c["source_url"]) for p in evidence_db()["products"] for c in p["claims"]}
        self.assertEqual(excel, records)

    def test_api_and_agent_tool(self):
        with TestClient(app) as client:
            result = client.post("/api/v1/member4/analyze", json={"text":"中等遮瑕，很服帖"})
            self.assertEqual(result.status_code,200)
            response = client.post("/api/v1/tools/text_integrity",json={"tool":"text_integrity", "request_id":"test", "payload":{"text":"中等遮瑕，很服帖"}})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()["evidence"]["member4_analysis"]["claims"],result.json()["claims"])
            self.assertEqual(client.post("/api/v1/member4/ocr",json={"media_ref":"../../app.py"}).status_code,422)

if __name__ == "__main__":
    unittest.main()
