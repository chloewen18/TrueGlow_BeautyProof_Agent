import json
import re
import openpyxl
from pathlib import Path

ANSWER_FILE = Path("/Users/gracehan/Downloads/Claim Extraction_Mock 2.1/30条盲测题.xlsx")
RESULT_FILE = Path("blind_test_v1_results.json")
REPORT_FILE = Path("blind_test_v1_score_report.json")


def split_expected_claims(value):
    if value is None:
        return []

    text = str(value).strip()

    # Answer Key 中多个 claim 主要使用 ; / ；分隔
    parts = re.split(r"[;；]", text)

    return [
        p.strip()
        for p in parts
        if p and p.strip()
    ]


def normalize_claim(value):
    if value is None:
        return ""

    text = str(value).strip().lower()

    # 去掉首尾空格及常见多余空白
    text = re.sub(r"\s+", " ", text)

    return text


def main():

    # -----------------------------
    # 读取系统预测
    # -----------------------------
    predictions = json.loads(
        RESULT_FILE.read_text(encoding="utf-8")
    )

    pred_by_id = {}

    for item in predictions:
        claims = []

        for c in item.get("claims", []):
            name = c.get("canonical_claim")

            if name:
                claims.append(normalize_claim(name))

        pred_by_id[item["id"]] = {
            "input_text": item.get("input_text"),
            "claims": claims,
            "raw_claims": item.get("claims", [])
        }

    # -----------------------------
    # 读取 Answer Key
    # -----------------------------
    wb = openpyxl.load_workbook(
        ANSWER_FILE,
        data_only=True
    )

    ws = wb["Answer Key"]

    rows = list(ws.iter_rows(values_only=True))

    header = rows[0]

    answer_by_id = {}

    for row in rows[1:]:

        if not row or not row[0]:
            continue

        item_id = str(row[0]).strip()

        expected_claims = split_expected_claims(row[1])

        answer_by_id[item_id] = {
            "expected_claims": expected_claims,
            "expected_polarity": row[2],
            "expected_duration": row[3],
            "expected_slang": row[4],
            "expected_exaggerated": row[5],
            "consumer_meaning": row[6],
            "why_case_matters": row[7],
        }

    # -----------------------------
    # Claim-level scoring
    # -----------------------------
    TP = 0
    FP = 0
    FN = 0

    details = []

    for item_id in sorted(answer_by_id.keys()):

        answer = answer_by_id[item_id]

        expected_original = answer["expected_claims"]

        expected = [
            normalize_claim(x)
            for x in expected_original
        ]

        prediction = pred_by_id.get(
            item_id,
            {
                "input_text": None,
                "claims": [],
                "raw_claims": []
            }
        )

        predicted = prediction["claims"]

        expected_set = set(expected)
        predicted_set = set(predicted)

        matched = sorted(
            expected_set & predicted_set
        )

        missed = sorted(
            expected_set - predicted_set
        )

        extra = sorted(
            predicted_set - expected_set
        )

        TP += len(matched)
        FN += len(missed)
        FP += len(extra)

        details.append({
            "id": item_id,
            "input_text": prediction["input_text"],
            "expected_claims": expected_original,
            "predicted_claims": predicted,
            "matched": matched,
            "missed": missed,
            "extra": extra,
            "expected_polarity_notes": answer["expected_polarity"],
            "expected_duration": answer["expected_duration"],
            "expected_slang": answer["expected_slang"],
            "expected_exaggerated": answer["expected_exaggerated"],
        })

    precision = (
        TP / (TP + FP)
        if (TP + FP)
        else 0
    )

    recall = (
        TP / (TP + FN)
        if (TP + FN)
        else 0
    )

    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall)
        else 0
    )

    report = {
        "summary": {
            "test_cases": len(answer_by_id),
            "true_positive_claims": TP,
            "false_positive_claims": FP,
            "false_negative_claims": FN,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        },
        "details": details,
    }

    REPORT_FILE.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    # -----------------------------
    # 输出结果
    # -----------------------------
    print("\n==============================")
    print("Blind Test v1 Claim-level Score")
    print("==============================")

    print("测试案例:", len(answer_by_id))
    print("TP:", TP)
    print("FP:", FP)
    print("FN:", FN)

    print(f"Precision: {precision:.2%}")
    print(f"Recall:    {recall:.2%}")
    print(f"F1:        {f1:.2%}")

    print("\n========== 错误明细 ==========")

    for d in details:

        if d["missed"] or d["extra"]:

            print("\n", d["id"])

            if d["missed"]:
                print("  漏检:", d["missed"])

            if d["extra"]:
                print("  误检:", d["extra"])

    print("\n==============================")
    print("评分报告:")
    print(REPORT_FILE.resolve())


if __name__ == "__main__":
    main()
