import json
import openpyxl
from pathlib import Path

from claim_extractor_mock_v2_1 import (
    ClaimExtractor,
    MockSemanticLayer,
    merge_rule_and_mock,
    resolve_claim_conflicts,
)

BLIND_TEST = Path("/Users/gracehan/Downloads/Claim Extraction_Mock 2.1/30条盲测题.xlsx")
DICTIONARY = Path("Foundation_Claim_Dictionary_V2_2_Separate_Slang_Exaggerated.xlsx")
OUTPUT = Path("blind_test_v1_results.json")


def extract_texts(ws):
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []

    # 自动寻找包含 B01/B02... 的测试行，避免依赖固定列名
    tests = []
    for row in rows:
        if not row:
            continue

        item_id = row[0]
        if isinstance(item_id, str) and item_id.upper().startswith("B"):
            try:
                num = int(item_id[1:])
            except ValueError:
                continue

            if 1 <= num <= 30:
                # 根据当前盲测表结构：第2列为待测原始文案
                text = row[1] if len(row) > 1 else None
                if text:
                    tests.append((item_id, str(text)))

    return tests


def run_claim(text, extractor, mock_layer):
    base = extractor.extract_claims(text)
    rule_claims = base["output"]["claims"]

    mock_claims = mock_layer.analyze(text, rule_claims)
    merged = merge_rule_and_mock(rule_claims, mock_claims)
    cleaned = resolve_claim_conflicts(text, merged)

    return cleaned


def main():
    wb = openpyxl.load_workbook(BLIND_TEST, data_only=True)

    extractor = ClaimExtractor(str(DICTIONARY))
    mock_layer = MockSemanticLayer(extractor.consumer_meaning)

    all_tests = []

    for ws in wb.worksheets:
        if ws.title.lower() == "instructions":
            continue
        all_tests.extend(extract_texts(ws))

    # 去重
    seen = set()
    tests = []
    for item_id, text in all_tests:
        if item_id not in seen:
            tests.append((item_id, text))
            seen.add(item_id)

    results = []

    for item_id, text in tests:
        claims = run_claim(text, extractor, mock_layer)

        result = {
            "id": item_id,
            "input_text": text,
            "claim_count": len(claims),
            "claims": claims,
        }
        results.append(result)

        print("=" * 60)
        print(item_id, text)
        print("claim_count:", len(claims))
        for claim in claims:
            print(
                " -",
                claim.get("canonical_claim"),
                "| polarity:", claim.get("polarity"),
                "| duration:", claim.get("duration"),
            )

    OUTPUT.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\n" + "=" * 60)
    print("Blind Test finished.")
    print("测试条数:", len(results))
    print("结果文件:", OUTPUT.resolve())


if __name__ == "__main__":
    main()
