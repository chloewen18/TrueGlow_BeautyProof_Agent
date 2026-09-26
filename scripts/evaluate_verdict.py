"""Verdict 级端到端评测：对配对数据集逐张跑完整 Main Agent（真实模型）。

对每一张图（原图 + 修饰图）用同一条宣称文案「原相机零滤镜」走完整核验链路
（上传 → 工具调用 → 融合 → 分级 → 报告），统计 verdict 级表现：

  - 原图（未修饰）：误指率 = verdict 为「高风险误导」的占比，目标为 0
  - 修饰图：信号捕获率 = verdict 为「部分可疑」或「高风险误导」的占比
  - 平均耗时

用法：
    python scripts/evaluate_verdict.py --limit 1     # 冒烟
    python scripts/evaluate_verdict.py --limit 30    # 30 对（约 60 张）
    python scripts/evaluate_verdict.py               # 全部 100 对

结果写入 data/verdict_evaluation.json。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import Counter
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # 允许直接 `python scripts/evaluate_verdict.py` 运行
    sys.path.insert(0, str(ROOT))
DATASET = ROOT / "data/datasets/FFHQ_FFHQR_100_pairs_v1"

SIGNALLED = {"partially_suspicious", "high_risk_misleading"}
FALSE_ACCUSATION = "高风险误导"


def count_verdicts(rows: list[dict]) -> dict:
    return dict(Counter(r.get("verdict") for r in rows if r.get("verdict")))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="取前 N 对；0 = 全部")
    parser.add_argument("--out", default=str(ROOT / "data/verdict_evaluation.json"))
    args = parser.parse_args()

    pairs: list[tuple[str, str]] = []
    with (DATASET / "paired_manifest.csv").open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            pairs.append((row["original_path"], row["retouched_path"]))
    if args.limit:
        pairs = pairs[: args.limit]
    print(f"待评测配对数：{len(pairs)}（共 {len(pairs) * 2} 张）", flush=True)

    # 延迟导入：确保 --help 等不需要加载模型
    from fastapi.testclient import TestClient

    from backend.app.main import app

    client = TestClient(app)
    rows: list[dict] = []

    for idx, (original_rel, retouched_rel) in enumerate(pairs, 1):
        for kind, rel in (("original", original_rel), ("retouched", retouched_rel)):
            path = DATASET / rel
            started = time.time()
            record: dict = {"pair": idx, "kind": kind, "file": rel}
            try:
                upload = client.post(
                    "/api/v1/upload",
                    files={"files": (path.name, path.read_bytes(), "image/png")},
                    timeout=120,
                )
                upload.raise_for_status()
                ref = upload.json()["uploaded"][0]["media_ref"]
                payload = {
                    "content_id": f"verdict_eval_{idx}_{kind}",
                    "content": {
                        "title": "上脸实测分享",
                        "body_text": "原相机零滤镜，无磨皮无修图，妆效自然持久",
                        "product": "某品牌粉底液",
                        "media": [{"kind": "image", "ref": ref}],
                        "comments": [],
                    },
                }
                response = client.post("/api/v1/verify", json=payload, timeout=600)
                response.raise_for_status()
                report = (response.json().get("result") or {}).get("report") or {}
                card = report.get("trust_card") or {}
                record["verdict"] = card.get("verdict")              # 英文枚举，用于统计
                record["verdict_label"] = card.get("verdict_label")  # 中文，用于展示
                record["tools"] = {c.get("tool"): c.get("status") for c in report.get("tool_calls", [])}
                record["latency_s"] = round(time.time() - started, 1)
                print(f"[{idx:>3}/{len(pairs)}] {kind:<9} {record['verdict_label']}  ({record['latency_s']}s)", flush=True)
            except Exception as exc:  # noqa: BLE001 - 评测需记录失败而非中断
                record["error"] = str(exc)
                record["latency_s"] = round(time.time() - started, 1)
                print(f"[{idx:>3}/{len(pairs)}] {kind:<9} ERROR {str(exc)[:120]}", flush=True)
            rows.append(record)

    originals = [r for r in rows if r.get("kind") == "original" and r.get("verdict")]
    retouched = [r for r in rows if r.get("kind") == "retouched" and r.get("verdict")]
    errors = [r for r in rows if r.get("error")]
    latencies = [r["latency_s"] for r in rows if "latency_s" in r]

    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "pairs_requested": len(pairs),
        "pairs_completed": len(rows) // 2,
        "claim_used": "原相机零滤镜，无磨皮无修图，妆效自然持久",
        "originals": {
            "n": len(originals),
            "false_accusation_rate": (
                round(sum(1 for r in originals if r["verdict"] == FALSE_ACCUSATION) / len(originals), 4)
                if originals else None
            ),
            "verdicts": count_verdicts(originals),
        },
        "retouched": {
            "n": len(retouched),
            "signal_capture_rate": (
                round(sum(1 for r in retouched if r["verdict"] in SIGNALLED) / len(retouched), 4)
                if retouched else None
            ),
            "verdicts": count_verdicts(retouched),
        },
        "errors": len(errors),
        "avg_latency_s": round(mean(latencies), 1) if latencies else None,
        "rows": rows,
    }

    out = Path(args.out)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    printable = {k: v for k, v in summary.items() if k != "rows"}
    print("\n===== 汇总 =====")
    print(json.dumps(printable, ensure_ascii=False, indent=2))
    print(f"\n已写入 {out}", flush=True)


if __name__ == "__main__":
    main()
