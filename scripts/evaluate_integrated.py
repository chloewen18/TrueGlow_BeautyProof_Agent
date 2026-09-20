"""Recompute auditable metrics from model outputs; never use mock signals."""
import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from importlib.metadata import version

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
from backend.app.integrations.visual import member3_engine, pair, sha256, trufor
from backend.app.integrations.member4.evaluate import evaluate
from backend.app.paths import MEMBER2_CURRENT, MEMBER4_CURRENT, MEMBER4_LEGACY


def binary_metrics(rows, threshold):
    valid = [r for r in rows if r.get("error") is None]
    tp = sum(r["label"] == 1 and r["score"] >= threshold for r in valid)
    fp = sum(r["label"] == 0 and r["score"] >= threshold for r in valid)
    tn = sum(r["label"] == 0 and r["score"] < threshold for r in valid)
    fn = sum(r["label"] == 1 and r["score"] < threshold for r in valid)
    return {"threshold": threshold, "attempted": len(rows), "completed": len(valid),
            "errors": len(rows)-len(valid), "tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "fpr": fp/(fp+tn) if fp+tn else None, "tpr": tp/(tp+fn) if tp+fn else None,
            "f1": 2*tp/(2*tp+fp+fn) if tp+fp+fn else None}


def member2_delivered():
    folder = MEMBER2_CURRENT / "_Output/npz"
    rows, unlabelled = [], []
    for path in sorted(folder.glob("*.npz")):
        name = path.name
        label = 1 if name == "tampered1.png.npz" else 0 if name.startswith(("ffhq_", "pristine")) else None
        if label is None:
            unlabelled.append(name)
            continue
        try:
            with np.load(path, allow_pickle=False) as data:
                score = float(data["score"])
                if not 0 <= score <= 1 or not np.isfinite(data["map"]).all() or not np.isfinite(data["conf"]).all():
                    raise ValueError("Invalid output values")
            group = "q20" if "q20" in name else "q50" if "q50" in name else "tampered" if label else "original"
            rows.append({"sample": name, "label": label, "score": score, "integrity_score": 1-score,
                         "group": group, "output_sha256": sha256(path), "error": None})
        except Exception as exc:
            rows.append({"sample": name, "label": label, "error": str(exc)})
    return {"mode": "delivered_real_outputs_recalculated", "metrics": binary_metrics(rows, .5),
            "groups": {g: binary_metrics([r for r in rows if r.get("group") == g], .5) for g in ("original", "q50", "q20", "tampered")},
            "rows": rows, "excluded_unknown_labels": unlabelled,
            "limitations": ["原始输入未随包完整提供，标签来自交付命名，无法独立核验输入或重跑这些文件。",
                            "按原始score越高越可疑重新计算；交付CSV列名方向有误。",
                            "同一人物及压缩派生图不独立；仅一个有明确命名的阳性，不用于推断泛化准确率。",
                            "0.5为预设展示阈值，不是从当前测试集挑选的最优阈值。"]}


def member3_current(limit):
    root = ROOT / "data/datasets/FFHQ_FFHQR_100_pairs_v1"
    with (root / "paired_manifest.csv").open(encoding="utf-8-sig", newline="") as file:
        manifest = list(csv.DictReader(file))[:limit]
    engine = member3_engine()
    rows, controls = [], []
    for index, entry in enumerate(manifest):
        for column, label in [("original_path", 0), ("retouched_path", 1)]:
            path = root / entry[column]
            try:
                output = engine.analyze_single(path)
                score = output["result"]["generic_retouch"]["score"]
                rows.append({"sample": entry[column], "pair_id": entry["pair_id"], "label": label,
                             "score": score, "input_sha256": sha256(path), "output": output, "error": None})
            except Exception as exc:
                rows.append({"sample": entry[column], "label": label, "error": str(exc)})
        if index < 10:
            path = root / entry["original_path"]
            try:
                controls.append({"sample": entry["pair_id"], "output": pair(path, path, "evaluation_identity"), "error": None})
            except Exception as exc:
                controls.append({"sample": entry["pair_id"], "error": str(exc)})
        print(f"Member3 {index+1}/{len(manifest)} pairs", flush=True)
    return {"mode": "local_real_inference", "metrics": binary_metrics(rows, engine.stage1_threshold),
            "rows": rows, "identity_controls": controls,
            "limitations": ["100对来源为FFHQR，成员三训练也用过该数据域；样本/身份重叠尚未排除，只能称探索性复测。",
                            "只有原图/修饰图真值，没有操作/强度/产品因果真值，不计算这些任务的准确率。",
                            "同图控制不代表真实不同帧负样本表现；保留条件估计原始输出。"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--member3-pairs", type=int, default=100)
    parser.add_argument("--trufor-live", action="store_true")
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = ROOT / "data/evaluation_runs" / stamp
    target.mkdir(parents=True)
    result = {"run_id": stamp, "created_at": datetime.now(timezone.utc).isoformat(),
              "member2": member2_delivered(), "member4": evaluate(), "member3": {"mode": "not_run"}}
    result["environment"] = {name: version(name) for name in ("torch", "torchvision", "numpy", "timm", "openpyxl")}
    result["input_versions"] = {str(path.relative_to(ROOT)): sha256(path) for path in [
        ROOT / "backend/app/integrations/member4/claim_extractor.py",
        ROOT / "backend/app/integrations/member4/service.py",
        MEMBER4_CURRENT / "Member4_Mini_Efficacy_Evidence_Library_v2.json",
        MEMBER4_CURRENT / "Foundation_Claim_Dictionary_V2_2_Separate_Slang_Exaggerated.xlsx",
        MEMBER4_LEGACY / "30条盲测题.xlsx",
        ROOT / "data/datasets/FFHQ_FFHQR_100_pairs_v1/paired_manifest.csv"]}
    if args.member3_pairs:
        result["member3"] = member3_current(args.member3_pairs)
    if args.trufor_live:
        root = ROOT / "data/datasets/FFHQ_FFHQR_100_pairs_v1"
        result["trufor_live"] = []
        for relative in ["originals/00001.png", "retouched/00001.png"]:
            try:
                result["trufor_live"].append({"sample": relative, "output": trufor(root / relative)})
            except Exception as exc:
                result["trufor_live"].append({"sample": relative, "error": str(exc)})
    serialized = json.dumps(result, ensure_ascii=False, indent=2)
    (target / "report.json").write_text(serialized, encoding="utf-8")
    temporary = target / "latest.tmp"
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(ROOT / "data/integrated_evaluation.json")
    (ROOT / "data/member4_evaluation.json").write_text(json.dumps(result["member4"], ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"run": stamp, "member2": result["member2"]["metrics"],
                      "member3": result["member3"].get("metrics"),
                      "member4_exact": {k: v["exact_match_count"] for k,v in result["member4"]["datasets"].items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
