"""Member 4 rules and local evidence adapter. No answer keys are loaded here."""
import json
from collections import Counter
from functools import lru_cache
from pathlib import Path
from openpyxl import load_workbook
from .claim_extractor import ClaimExtractor, MockSemanticLayer, merge_rule_and_mock, resolve_claim_conflicts
from .full_pipeline import add_bridge_rules, evidence_matches_for_claim

ASSETS = Path(__file__).resolve().parents[4] / "data/deliverables/member4"

@lru_cache(maxsize=1)
def extractor():
    return ClaimExtractor(str(ASSETS / "Claim Dictionary V2.2.xlsx"))

@lru_cache(maxsize=1)
def evidence_db():
    return json.loads((ASSETS / "Mini功效证据JSON.json").read_text(encoding="utf-8-sig"))

def workbook_rows(filename, sheet=None):
    with (ASSETS / filename).open("rb") as file:
        book = load_workbook(file, read_only=True, data_only=True)
        rows = list((book[sheet] if sheet else book.worksheets[0]).values)
        book.close()
    return [dict(zip(rows[0], row)) for row in rows[1:] if any(v is not None for v in row)]

def analyze(text, product="", comments=None):
    engine = extractor()
    base = engine.extract_claims(text)["output"]["claims"]
    semantic = MockSemanticLayer(engine.consumer_meaning).analyze(text, base)
    claims = add_bridge_rules(text, resolve_claim_conflicts(text, merge_rule_and_mock(base, semantic)), engine.consumer_meaning)
    for claim in claims:
        matches = evidence_matches_for_claim(evidence_db(), claim["canonical_claim"], product)
        supports = bool(matches) and claim["polarity"] == "positive"
        claim["evidence_matches"] = matches
        claim["evidence_supported"] = supports
        claim["audience_explanation"] = (
            "交付证据库有同产品同功效的品牌资料；未在线复核，也不代表个人效果已验证。"
            if supports else "当前产品及宣称未获得本地证据支持；不等于该说法为假。")
    counts = Counter(c.strip() for c in (comments or []) if c.strip())
    return {"mode": "dictionary_rules_mock_semantic", "text": text, "product": product,
            "claims": claims, "comment_analysis": {
                "count": sum(counts.values()), "repeated_phrases": {k:v for k,v in counts.items() if v > 1},
                "note": "重复评论只提示独立参考价值有限，不判定为假评论，也不作为功效证明。"},
            "evidence_note": evidence_db()["important_note"]}
