"""Evaluate predictions first, then compare canonical sets with supplied keys."""
import json
from pathlib import Path
from .service import analyze, workbook_rows


def evaluate():
    output = {}
    for filename, sheet, text_column in [("20条测试题.xlsx", "Test Set", "Test Text"),
                                         ("30条盲测题.xlsx", "Blind Test", "Blind Test Text")]:
        rows = workbook_rows(filename, sheet)
        predictions = []
        for row in rows:
            try:
                claims = analyze(row[text_column])["claims"]
                predictions.append((row, {c["canonical_claim"] for c in claims}, None))
            except Exception as exc:
                predictions.append((row, set(), str(exc)))
        keys = {r["ID"]: r for r in (workbook_rows(filename, "Answer Key") if sheet == "Blind Test" else rows)}
        cases = []
        tp = fp = fn = exact = 0
        for row, predicted, error in predictions:
            expected = {v.strip() for v in keys[row["ID"]]["Expected Canonical Claims"].replace("；", ";").split(";") if v.strip()}
            tp += len(expected & predicted)
            fp += len(predicted - expected)
            fn += len(expected - predicted)
            exact += int(expected == predicted and error is None)
            cases.append({"id": row["ID"], "text": row[text_column], "expected": sorted(expected),
                          "predicted": sorted(predicted), "missing": sorted(expected-predicted),
                          "extra": sorted(predicted-expected), "error": error})
        output[sheet] = {"count":len(cases), "exact_match_count":exact,
                         "exact_match_rate":exact/len(cases), "micro_f1":2*tp/(2*tp+fp+fn) if tp+fp+fn else 0,
                         "errors":sum(c["error"] is not None for c in cases), "cases":cases}
    return {"mode":"real_rules", "engine":"member4_final_v2", "scope":"canonical claim sets only; no OCR/polarity/evidence validation; previously used development sets, not an independent blind benchmark",
            "datasets":output}

if __name__ == "__main__":
    result = evaluate()
    target = Path("data/member4_evaluation.json")
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k:{m:v for m,v in s.items() if m != "cases"} for k,s in result["datasets"].items()}, ensure_ascii=False))
