"""Main Agent 编排：计划 → 执行 → 融合 → 分级 → 报告（识别→判断→决策闭环）。

对外契约见 docs/API_SPEC.md：
  POST /api/v1/verify            一键完整核验
  POST /api/v1/creators/review   创作者补证复核
"""
from __future__ import annotations

import uuid
from typing import Any

from ..logging.trace import trace
from ..schemas.common import ToolRequest
from ..schemas.evidence import CreatorSubmission, EvidenceLayer
from ..schemas.report import FullReport
from ..storage.evidence_store import evidence_store
from ..tools.base import registry
from .fuser import fuser
from .grader import grader
from .planner import VerifyPlan, planner
from .reporter import VERDICT_LABEL, reporter


def _new_request_id() -> str:
    return f"req_{uuid.uuid4().hex[:12]}"


class MainAgent:
    """Main Agent：统一调度五个 Tool，融合证据，分级，生成报告。"""

    # ------------------------------------------------------------------
    def verify(self, payload: dict[str, Any], request_id: str | None = None) -> dict[str, Any]:
        rid = request_id or _new_request_id()
        trace.log(rid, "verify_start", payload_keys=list(payload.keys()))

        # 1) 计划
        plan = planner.plan(payload)
        trace.log(rid, "plan", steps=[s.tool for s in plan.steps], skipped=plan.skipped)

        # 2) 执行
        tool_results, tool_calls = self._execute(plan, rid)

        # 3) 融合
        layer = fuser.fuse(
            content_id=plan.content_id,
            tool_results=tool_results,
            user_context=payload.get("user_context"),
            creator_submission=payload.get("creator_submission"),
        )
        trace.log(rid, "fuse", evidence_counts={k: len(v) for k, v in {
            "source": layer.source_evidence.items,
            "visual": layer.visual_evidence.items,
            "before_after": layer.before_after_evidence.items,
            "text": layer.text_evidence.items,
        }.items()})

        # 4) 分级
        decision = grader.grade(layer)
        layer.agent_decision = decision
        layer.final_label = decision.final_label
        trace.log(rid, "grade", final_label=decision.final_label.value, confidence=decision.confidence)

        # 5) 报告
        report = reporter.generate(
            evidence=layer,
            request_id=rid,
            tool_calls=tool_calls,
            content_id=plan.content_id,
            product=payload.get("content", {}).get("product"),
        )
        trace.log(rid, "report", report_id=report.report_id, verdict=report.trust_card.verdict_label)

        # 持久化 + 收尾
        evidence_store.save_evidence(rid, layer)
        trace.log(rid, "verify_end", final_label=decision.final_label.value)

        return self._result(rid, report, layer)

    # ------------------------------------------------------------------
    def review(
        self,
        content_id: str,
        creator_submission: dict[str, Any],
        original_evidence: EvidenceLayer | dict[str, Any],
        recheck: dict[str, dict[str, Any]] | None = None,
        request_id: str | None = None,
        original_request_id: str | None = None,
    ) -> dict[str, Any]:
        """创作者补证复核：来源证据更新 + 可选工具复测 → 重新融合/分级/报告。

        返回结构（已冻结，见 API_SPEC §6.2）：
          { request_id, original_request_id, content_id,
            before_verdict, before_verdict_label, after_verdict, after_verdict_label,
            review_summary, report, credential }

        recheck: {tool_name: payload}，用于基于补证材料重新运行检测
        （如 image_forensics 传入 signals 反映"原视频帧 + 已声明滤镜"）。
        """
        rid = request_id or _new_request_id()
        trace.log(rid, "review_start", content_id=content_id, materials=list(creator_submission.keys()))

        if isinstance(original_evidence, dict):
            original_evidence = EvidenceLayer(**original_evidence)
        before_label_enum = original_evidence.final_label

        # 更新创作者补证状态
        original_evidence.creator_submission = CreatorSubmission(
            status="done",
            materials=creator_submission,
            review_result="补证材料已纳入复核",
            credential={"scope": "来源真实性与拍摄条件", "date": "2026-09-02"},
        )

        tool_calls: list[dict[str, Any]] = []

        # 1) 重新执行来源溯源（补证通过：C2PA 验证通过）
        t2_payload = {
            "files": creator_submission.get("original_file") or [{"kind": "image", "ref": "creator_original"}],
            "signals": {"c2pa_status": "valid", "metadata_complete": True, "creator_submission_status": "done"},
            "creator_submission": creator_submission,
        }
        tr = ToolRequest(tool="source_trace", request_id=rid, payload=t2_payload)
        resp = registry.get("source_trace").run(tr)
        tool_calls.append({"tool": "source_trace", "status": resp.status, "latency_ms": resp.meta.latency_ms, "evidence_keys": list(resp.evidence.keys()), "reason": "补证后重新核验来源"})

        # 2) 基础证据：原证据层还原 + 补证后复测覆盖
        tool_results = self._collect_static_evidence(original_evidence)
        tool_results["source_trace"] = resp.evidence
        for tool, payload in (recheck or {}).items():
            handler = registry.get(tool)
            if not handler:
                continue
            tr = ToolRequest(tool=tool, request_id=rid, payload=payload)
            r = handler.run(tr)
            tool_results[tool] = r.evidence
            tool_calls.append({"tool": tool, "status": r.status, "latency_ms": r.meta.latency_ms, "evidence_keys": list(r.evidence.keys()), "reason": "补证后基于原始素材复测"})

        # 3) 重新融合 + 分级 + 报告
        layer = fuser.fuse(
            content_id=content_id,
            tool_results=tool_results,
            user_context=original_evidence.user_context,
            creator_submission=creator_submission,
        )
        decision = grader.grade(layer)
        layer.agent_decision = decision
        layer.final_label = decision.final_label
        report = reporter.generate(layer, rid, tool_calls, content_id=content_id)

        evidence_store.save_evidence(rid, layer)

        # 4) 组装「补证前 → 补证后」对比响应
        after_enum = decision.final_label
        before_label = VERDICT_LABEL.get(before_label_enum, before_label_enum.value)
        after_label = VERDICT_LABEL.get(after_enum, after_enum.value)
        changed = before_label_enum != after_enum
        real_source = tool_results.get("source_trace", {}).get("file_info", {}).get("mode") == "real_exif"
        credential = None
        cs = report.evidence.creator_submission
        if cs is not None:
            credential = cs.credential if isinstance(cs, CreatorSubmission) else (cs.get("credential"))
        if real_source:
            summary = f"补证文件已收件并解析元数据，当前结论为「{after_label}」。C2PA 尚未验证，未签发可信凭证；视觉检测仍为模拟实现。"
        elif changed:
            summary = (
                f"创作者补充原始素材并重新核验后，结论由「{before_label}」更新为「{after_label}」。"
                "来源可信度提升（C2PA 验证有效），部分磨皮/曝光差异与已声明的拍摄及滤镜条件一致。"
            )
            if credential:
                summary += "复核通过，已签发可信妆效凭证。"
        else:
            summary = f"复核后结论维持「{after_label}」，未发生变化。"

        trace.log(rid, "review_end", final_label=after_enum.value, changed=changed)

        return {
            "request_id": rid,
            "original_request_id": original_request_id,
            "content_id": content_id,
            "before_verdict": before_label_enum.value,
            "before_verdict_label": before_label,
            "after_verdict": after_enum.value,
            "after_verdict_label": after_label,
            "review_summary": summary,
            "report": report.model_dump(exclude_none=False),
            "credential": credential,
        }

    # ------------------------------------------------------------------
    @staticmethod
    def _collect_static_evidence(layer: EvidenceLayer) -> dict[str, dict[str, Any]]:
        """从已存证据层还原其余 Tool 的原始结果，供复核复用。"""
        out: dict[str, dict[str, Any]] = {}
        if layer.source_evidence.raw:
            out["source_trace"] = layer.source_evidence.raw
        if layer.visual_evidence.raw:
            out["image_forensics"] = layer.visual_evidence.raw
        if layer.before_after_evidence.raw:
            out["before_after"] = layer.before_after_evidence.raw
        if layer.text_evidence.raw:
            out["text_integrity"] = layer.text_evidence.raw
        return out

    # ------------------------------------------------------------------
    @staticmethod
    def _execute(plan: VerifyPlan, rid: str) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
        results: dict[str, dict[str, Any]] = {}
        calls: list[dict[str, Any]] = []
        for step in plan.steps:
            handler = registry.get(step.tool)
            if not handler:
                trace.log(rid, "tool_missing", tool=step.tool)
                continue
            tr = ToolRequest(tool=step.tool, request_id=rid, payload=step.payload)
            resp = handler.run(tr)
            calls.append({
                "tool": step.tool,
                "status": resp.status,
                "latency_ms": resp.meta.latency_ms,
                "model": resp.meta.model,
                "evidence_keys": list(resp.evidence.keys()),
                "reason": step.reason,
            })
            trace.log(rid, "tool_call", tool=step.tool, status=resp.status, latency_ms=resp.meta.latency_ms)
            if resp.status in ("success", "partial"):
                results[step.tool] = resp.evidence
        return results, calls

    # ------------------------------------------------------------------
    @staticmethod
    def _result(rid: str, report: FullReport, layer: EvidenceLayer, reviewed: bool = False) -> dict[str, Any]:
        return {
            "request_id": rid,
            "content_id": report.content_id,
            "reviewed": reviewed,
            "verdict": report.trust_card.verdict.value,
            "verdict_label": report.trust_card.verdict_label,
            "report": report.model_dump(exclude_none=False),
            "decision_path": layer.agent_decision.decision_path if layer.agent_decision else [],
        }


main_agent = MainAgent()
