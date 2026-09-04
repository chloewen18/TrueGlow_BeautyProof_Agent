"""TrueGlow 映真 - Demo CLI：跑通「识别 → 判断 → 决策」完整闭环。

用法：
  cd backend
  ../.venv/bin/python -m demo.run_demo          # 跑全部案例（A/B + C 补证复核）
  ../.venv/bin/python -m demo.run_demo case_a   # 只跑案例 A
"""
from __future__ import annotations

import json
import sys

from app.agent.orchestrator import main_agent
from app.storage.evidence_store import evidence_store

from .cases import ALL_CASES, CASE_B, CASE_C_SUBMISSION

sys.path.insert(0, ".")


def _summary(result: dict, is_review: bool = False) -> None:
    if is_review:
        print(f"  ▶ 复核结论：{result['after_verdict_label']}（{result['after_verdict']}）")
        print(f"  ▶ 补证前：{result['before_verdict_label']}（{result['before_verdict']}）")
        print(f"  ▶ request_id：{result['request_id']}（原 {result.get('original_request_id')}）")
        print(f"  ▶ 复核说明：{result['review_summary']}")
        decision_path = (result["report"].get("evidence", {}).get("agent_decision", {}) or {}).get("decision_path", [])
    else:
        print(f"  ▶ 结论：{result['verdict_label']}（{result['verdict']}）")
        print(f"  ▶ request_id：{result['request_id']}")
        decision_path = result.get("decision_path", [])
    card = result["report"]["trust_card"]
    print("  ▶ 主要发现：")
    for f in card["main_findings"]:
        print(f"      - {f}")
    print("  ▶ 信任卡区块：")
    for s in card["sections"]:
        print(f"      [{s['title']}] {'；'.join(s['content'])}")
    print("  ▶ 决策路径（节选）：")
    for p in decision_path[-4:]:
        print(f"      - {p}")


def run_case_a() -> dict:
    print("=" * 72)
    print("案例 A：真实但缺少来源信息（预期：证据不足，不误判伪造）")
    print("=" * 72)
    r = main_agent.verify(ALL_CASES["case_a"])
    _summary(r)
    return r


def run_case_b() -> dict:
    print("=" * 72)
    print("案例 B：After 图磨皮 + 曝光变化 + 宣称「原相机零滤镜」（预期：高风险误导）")
    print("=" * 72)
    r = main_agent.verify(CASE_B)
    _summary(r)
    return r


def run_case_c(b_request_id: str) -> dict:
    print("=" * 72)
    print("案例 C：创作者提交原始视频后复核（预期：结论更新为部分可疑 + 可信妆效凭证）")
    print("=" * 72)
    submission = {**CASE_C_SUBMISSION, "original_request_id": b_request_id}
    rr = main_agent.review(
        submission["content_id"],
        submission["creator_submission"],
        evidence_store.load_evidence(b_request_id),
        recheck=submission.get("recheck"),
        original_request_id=b_request_id,
    )
    _summary(rr, is_review=True)
    cred = rr.get("credential")
    print("  ▶ 可信妆效凭证：", json.dumps(cred, ensure_ascii=False))
    return rr


def main() -> None:
    target = sys.argv[1] if len(sys.argv) > 1 else "all"
    if target in ("case_a", "a", "A", "all"):
        run_case_a()
    if target in ("case_b", "b", "B", "all"):
        b = run_case_b()
    if target in ("case_c", "c", "C", "all"):
        run_case_c(b["request_id"] if "b" in locals() else run_case_b()["request_id"])
    print("\n完成。证据与日志已落盘到 backend/data/（evidence/ 与 logs/）。")


if __name__ == "__main__":
    main()
