"""证据融合：把各 Tool 的结构化证据汇总为统一证据层（EvidenceLayer）。

职责：
  - 将各 Tool 的 evidence dict 转为 EvidenceItem（含可解释依据、可靠性、来源）
  - 处理证据之间的一致、冲突与缺失（记录 note，不武断抹平）
  - 输出 tool_reliability 汇总，供分级模块参考

冲突处理原则（方案文档第七节）：
  - C2PA 缺失 ≠ 伪造：T2 的 Unknown 不会自动推高内容完整性风险
  - 检测结果必须结合可靠性：如 Skin smoothing High 但 Reliability Medium，风险要降档
  - 证据不足时倾向 insufficient_evidence，不做二元判假
"""
from __future__ import annotations

from typing import Any

from ..schemas.common import EvidenceItem, EvidenceReliability, FinalLabel, ToolReliabilityMap
from ..schemas.evidence import (
    AgentDecision,
    BeforeAfterEvidenceLayer,
    CreatorSubmission,
    EvidenceLayer,
    SourceEvidenceLayer,
    TextEvidenceLayer,
    VisualEvidenceLayer,
)
from ..schemas.tools import (
    BeforeAfterEvidence,
    ImageForensicsEvidence,
    PageUnderstandingEvidence,
    SourceTraceEvidence,
    TextIntegrityEvidence,
)

_TOOL_LABELS = {
    "page_understanding": "页面理解与任务拆解",
    "source_trace": "来源溯源",
    "image_forensics": "图像鉴伪",
    "before_after": "前后对比",
    "text_integrity": "文本与功效证据",
}


def _ev(evidence_id: str, tool: str, claim: str, finding: dict[str, Any], reliability: EvidenceReliability, source: str | None = None, note: str | None = None) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id, tool=tool, claim=claim, finding=finding,
        reliability=reliability, source=source, confidence_note=note,
    )


class EvidenceFuser:
    """把各 Tool 结果融合为 EvidenceLayer。"""

    def fuse(
        self,
        content_id: str,
        tool_results: dict[str, dict[str, Any]],
        user_context: dict[str, Any] | None = None,
        creator_submission: dict[str, Any] | None = None,
    ) -> EvidenceLayer:
        layer = EvidenceLayer(content_id=content_id, user_context=user_context or {})
        if creator_submission:
            layer.creator_submission = CreatorSubmission(
                status="done",
                materials=creator_submission,
                review_result="补证材料已纳入复核",
                credential={"scope": "来源与拍摄条件", "date": "2026-09-02"},
            )
        notes: list[str] = []

        # ---- T1 页面理解（决策上下文，不入证据层 items，但影响任务拆解）----
        t1 = tool_results.get("page_understanding")
        t1_ev: PageUnderstandingEvidence | None = PageUnderstandingEvidence(**t1) if t1 else None

        # ---- T2 来源溯源 ----
        t2 = tool_results.get("source_trace")
        if t2:
            e = SourceTraceEvidence(**t2)
            c2pa = e.c2pa.status
            if c2pa == "valid":
                items = [_ev("src-001", "source_trace", "C2PA 存在且验证通过，来源证据可靠", {"c2pa_status": "valid"}, EvidenceReliability.HIGH, "C2PA / Content Credentials")]
            elif c2pa == "invalid":
                items = [_ev("src-001", "source_trace", "C2PA 签名验证失败，来源证据不可信", {"c2pa_status": "invalid"}, EvidenceReliability.HIGH, "C2PA / Content Credentials")]
            else:
                items = [_ev("src-001", "source_trace", "C2PA 不存在，来源状态 Unknown（不等于伪造）", {"c2pa_status": "absent"}, EvidenceReliability.MEDIUM, "C2PA / Content Credentials", "元数据缺失可能受平台压缩/转码影响")]
            for i, a in enumerate(e.metadata_anomalies):
                items.append(_ev(f"src-002-{i}", "source_trace", f"元数据异常：{a}", {"anomaly": a}, EvidenceReliability.MEDIUM, "EXIF/XMP"))
            layer.source_evidence = SourceEvidenceLayer(summary=e.conclusion, items=items, raw=e.model_dump(exclude_none=True))

        # ---- T3 图像鉴伪 ----
        t3 = tool_results.get("image_forensics")
        if t3:
            e = ImageForensicsEvidence(**t3)
            items: list[EvidenceItem] = []
            for attr, label in [("local_replacement", "局部替换"), ("splicing", "拼接"), ("inpainting", "inpainting/局部生成")]:
                status = getattr(e, attr).value
                if status != "Not detected":
                    items.append(_ev(f"vis-{attr}", "image_forensics", f"检出{label}: {status}", {attr: status}, e.reliability, "TruFor/取证模型"))
            if e.ai_generated.value != "Unknown" and e.ai_generated.value != "Not detected":
                items.append(_ev("vis-ai", "image_forensics", f"AI 生成痕迹: {e.ai_generated.value}", {"ai_generated": e.ai_generated.value}, e.reliability))
            for attr, label in [("skin_smoothing", "皮肤平滑"), ("texture_loss", "纹理损失"), ("whitening", "美白/提亮"), ("face_reshape", "人脸重塑"), ("exposure_shift", "曝光偏移")]:
                sev = getattr(e, attr).value
                if sev in ("Medium", "High"):
                    items.append(_ev(f"vis-{attr}", "image_forensics", f"{label}: {sev}", {attr: sev}, e.reliability, "底妆专项分类器", "需结合 reliability 综合判断"))
            if not items:
                items = [_ev("vis-none", "image_forensics", "未检出明显篡改/修饰痕迹", {"integrity_score": e.integrity_score}, e.reliability, "TruFor/取证模型")]
            layer.visual_evidence = VisualEvidenceLayer(
                summary=f"完整性评分 {e.integrity_score:.2f}，可靠性 {e.reliability.value}",
                items=items, raw=e.model_dump(exclude_none=True),
            )

        # ---- T4 前后对比 ----
        t4 = tool_results.get("before_after")
        if t4:
            e = BeforeAfterEvidence(**t4)
            items = []
            for d in e.dimensions:
                if d.level.value != "Similar":
                    items.append(_ev(f"ba-{d.dimension}", "before_after", f"{d.dimension}: {d.level.value}（{d.detail}）", {"dimension": d.dimension, "level": d.level.value, "detail": d.detail}, e.comparison_reliability, "条件差异计算"))
            if not items:
                items = [_ev("ba-none", "before_after", "前后对比条件基本一致", {"comparison_reliability": e.comparison_reliability.value}, e.comparison_reliability, "条件差异计算")]
            layer.before_after_evidence = BeforeAfterEvidenceLayer(
                summary=f"可比较性 {e.comparison_reliability.value}；{e.attribution_summary}",
                items=items, raw=e.model_dump(exclude_none=True),
            )
            # 归因强度低时记录一条关键证据
            if e.attribution_strength.value in ("Weak", "Moderate"):
                layer.before_after_evidence.items.append(
                    _ev("ba-attribution", "before_after", f"妆效归因强度: {e.attribution_strength.value}（{e.attribution_summary}）", {"attribution_strength": e.attribution_strength.value}, e.comparison_reliability, "Beauty Effect Attribution")
                )

        # ---- T5 文本与功效证据 ----
        t5 = tool_results.get("text_integrity")
        if t5:
            e = TextIntegrityEvidence(**t5)
            items = []
            for c in e.claims:
                if c.severity.value in ("Medium", "High"):
                    items.append(_ev(f"txt-claim-{c.text[:8]}", "text_integrity", f"宣称「{c.text}」需重点核验", {"claim": c.text, "kind": c.kind, "severity": c.severity.value}, EvidenceReliability.MEDIUM))
            for i in e.integrity_issues:
                items.append(_ev(f"txt-issue-{i.type}", "text_integrity", i.detail, {"type": i.type, "severity": i.severity.value}, EvidenceReliability.MEDIUM))
            if not items and e.disclosure != "found":
                items = [_ev("txt-none", "text_integrity", "未发现明显文本完整性问题", {"disclosure": e.disclosure}, EvidenceReliability.MEDIUM)]
            layer.text_evidence = TextEvidenceLayer(
                summary=f"披露声明: {e.disclosure}；问题数: {len(e.integrity_issues)}",
                items=items, raw=e.model_dump(exclude_none=True),
            )
            layer.efficacy_evidence = [x.model_dump(exclude_none=True) for x in e.efficacy_evidence]

        # ---- 工具可靠性汇总 ----
        layer.tool_reliability = [
            ToolReliabilityMap(tool=tool, status="success", reliability=EvidenceReliability.MEDIUM)
            for tool in tool_results
        ]
        # 若某个 Tool 未返回（计划跳过/失败），记录缺失
        for tool in _TOOL_LABELS:
            if tool not in tool_results:
                layer.tool_reliability.append(
                    ToolReliabilityMap(tool=tool, status="missing", reliability=EvidenceReliability.LOW, note="未调用，相关维度证据缺失")
                )

        # ---- 冲突与缺失处理 ----
        # 冲突 1：宣称"原相机/零滤镜" vs 视觉检出修饰（T3/T5 交叉）
        if t5 and t3:
            t5e = TextIntegrityEvidence(**t5)
            t3e = ImageForensicsEvidence(**t3)
            declared_raw = any("原相机" in (i.detail or "") or "零滤镜" in (i.detail or "") for i in t5e.integrity_issues)
            visual_mod = t3e.skin_smoothing.value in ("Medium", "High") or t3e.local_replacement.value != "Not detected"
            if declared_raw and visual_mod:
                notes.append("冲突：文案宣称原相机/零滤镜，但视觉证据检出修饰痕迹——该宣称直接存疑")
        # 冲突 2：C2PA invalid + 其余证据
        if t2:
            t2e = SourceTraceEvidence(**t2)
            if t2e.c2pa.status == "invalid":
                notes.append("来源证据失败：C2PA 签名无效，内容完整性风险上调")
        # 缺失：T4 需要 before/after 对，若未提供则归因维度缺失
        if "before_after" not in tool_results and (t1_ev and "before_after_consistency" in (t1_ev.media_tasks or [])):
            notes.append("证据缺失：内容类型需要前后对比核验，但未提供 before/after 素材，妆效归因无法判断")

        # 把冲突/缺失说明挂到 agent_decision 之前的暂存区（grader 读取）
        layer.agent_decision = AgentDecision(
            final_label=FinalLabel.INSUFFICIENT_EVIDENCE,
            content_integrity_risk="待分级",
            attribution_reliability="待分级",
            claim_evidence_sufficiency="待分级",
            confidence="待分级",
            decision_path=["evidence_fusion"] + notes,
        )
        return layer


fuser = EvidenceFuser()
