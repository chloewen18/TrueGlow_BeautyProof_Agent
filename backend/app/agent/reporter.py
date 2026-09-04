"""报告生成：full_report（完整核验报告）+ trust_card（Beauty Trust Card）。

- 面向消费者：trust_card 用通俗语言回答"这是真的吗/哪里可疑/效果是不是产品造成的/我怎么理解"
- 面向高级用户/平台：full_report 携带完整证据链、Tool 结果、可靠性、决策路径
- LLM 可插拔：默认规则模板；配置 deepseek 后由 LLM 组织解释（失败自动降级模板）
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from ..config import settings
from ..llm import get_provider
from ..schemas.common import FinalLabel
from ..schemas.evidence import EvidenceLayer
from ..schemas.report import FullReport, TrustCard, TrustCardSection

VERDICT_LABEL = {
    FinalLabel.VERIFIED: "已验证",
    FinalLabel.PARTIALLY_SUSPICIOUS: "部分可疑",
    FinalLabel.INSUFFICIENT_EVIDENCE: "证据不足",
    FinalLabel.HIGH_RISK_MISLEADING: "高风险误导",
}

# 风险 → 底妆实际影响映射（方案文档 Tool5 用户解释阶段）
IMPACT_MAP = {
    "skin_smoothing": "磨皮可能遮盖卡纹、起皮和毛孔堆积，让遮瑕/服帖度看起来更好",
    "texture_loss": "纹理损失可能让皮肤状态看起来比实际更好",
    "whitening": "提亮/美白处理可能高估均匀肤色与提亮效果",
    "exposure_shift": "曝光变化可能让遮瑕、提亮和均匀肤色效果看起来更强",
    "face_reshape": "脸型/五官调整不属于产品效果，应忽略相关宣称",
}


class ReportGenerator:
    def __init__(self) -> None:
        self.provider = get_provider(settings.llm_provider)

    # ------------------------------------------------------------------
    def generate(
        self,
        evidence: EvidenceLayer,
        request_id: str,
        tool_calls: list[dict[str, Any]] | None = None,
        content_id: str | None = None,
        product: str | None = None,
    ) -> FullReport:
        cid = content_id or evidence.content_id or f"content_{uuid.uuid4().hex[:8]}"
        decision = evidence.agent_decision
        final_label = decision.final_label if decision else FinalLabel.INSUFFICIENT_EVIDENCE
        label = VERDICT_LABEL.get(final_label, final_label.value)

        main_findings = self._main_findings(evidence, decision.affected_claims if decision else [])
        sections = self._sections(evidence, final_label)
        creator_actions = self._creator_actions(evidence)
        advanced = self._advanced(evidence)
        limitations = self._limitations(evidence, final_label)

        # LLM 增强：组织自然语言解释（失败降级模板）
        if self.provider.name == "deepseek" and self.provider.is_available():
            sections = self._llm_enhance(evidence, sections) or sections

        # 产品名：优先取 t1/t5 识别结果，其次入参
        product = (
            product
            or (evidence.text_evidence.raw.get("product"))
            or (evidence.source_evidence.raw.get("file_info", {}).get("product"))
        )
        trust_card = TrustCard(
            request_id=request_id,
            content_id=cid,
            verdict=final_label,
            verdict_label=label,
            product=product,
            main_findings=main_findings,
            sections=sections,
            creator_actions=creator_actions,
            advanced=advanced,
            generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )

        return FullReport(
            report_id=f"report_{uuid.uuid4().hex[:12]}",
            request_id=request_id,
            content_id=cid,
            evidence=evidence,
            trust_card=trust_card,
            tool_calls=tool_calls or [],
            limitations=limitations,
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _main_findings(evidence: EvidenceLayer, affected_claims: list[str]) -> list[str]:
        findings: list[str] = []
        # 视觉/前后对比证据
        for item in evidence.visual_evidence.items:
            f = item.finding
            sev = f.get("skin_smoothing") or f.get("texture_loss") or f.get("whitening") or f.get("exposure_shift")
            if sev in ("Medium", "High"):
                findings.append(f"画面检出{sev.value if hasattr(sev, 'value') else sev}强度修饰痕迹：{item.claim}")
        for item in evidence.before_after_evidence.items:
            if item.finding.get("level") in ("Different", "Significant difference"):
                findings.append(f"前后对比不一致：{item.finding.get('detail') or item.claim}")
        # 文本问题
        for item in evidence.text_evidence.items:
            if item.finding.get("severity") == "High":
                findings.append(item.claim)
        # 受影响宣称
        for c in affected_claims[:5]:
            if not any(c in f for f in findings):
                findings.append(f"宣称存疑：{c}")
        if not findings:
            findings.append("未发现足以影响主要结论的可疑处理痕迹")
        return findings[:6]

    # ------------------------------------------------------------------
    def _sections(self, evidence: EvidenceLayer, label: FinalLabel) -> list[TrustCardSection]:
        sections: list[TrustCardSection] = []

        # 1) 这会怎样影响你？
        impact: list[str] = []
        for item in evidence.visual_evidence.items:
            for key, text in IMPACT_MAP.items():
                if item.finding.get(key) in ("Medium", "High") and text not in impact:
                    impact.append(text)
        for item in evidence.before_after_evidence.items:
            if item.finding.get("level") == "Significant difference" and "前后" in item.claim:
                impact.append("前后拍摄条件不一致会干扰对产品真实效果的判断")
        if not impact:
            impact.append("当前证据未显示明显会影响判断的加工痕迹")

        # 2) 哪些信息仍可参考？
        if label == FinalLabel.VERIFIED:
            reference = ["内容整体可信，产品宣称有较完整证据支持"]
        elif label == FinalLabel.PARTIALLY_SUSPICIOUS:
            reference = [
                "上妆步骤和产品用量仍有一定参考价值",
                "不建议只根据当前画面判断遮瑕与服帖度",
            ]
        elif label == FinalLabel.HIGH_RISK_MISLEADING:
            reference = ["该内容核心功效表达存疑，建议谨慎参考并交叉验证其他来源"]
        else:
            reference = ["需要补充原始素材后才能给出更明确的判断", "当前结论不代表内容一定造假"]

        sections.append(TrustCardSection(title="这会怎样影响你？", content=impact))
        sections.append(TrustCardSection(title="哪些信息仍可参考？", content=reference))

        # 3) 肤质定制建议
        skin = (evidence.user_context or {}).get("skin_type")
        if skin:
            advice = [f"如果你是{skin}肤质：建议重点观察遮瑕边界、纹理细节与持妆表现，尽量参考相同光线下的近距离画面"]
            sections.append(TrustCardSection(title=f"如果你是{skin}初学者", content=advice))
        return sections

    # ------------------------------------------------------------------
    @staticmethod
    def _creator_actions(evidence: EvidenceLayer) -> list[str]:
        base = ["原始视频/未压缩图片", "滤镜参数与拍摄设置", "同条件复测片段"]
        if evidence.creator_submission.status in ("received", "processing", "done"):
            return ["已提交补证材料，系统将重新核验", "复核通过后可获得「可信妆效凭证」"]
        return base

    # ------------------------------------------------------------------
    def _advanced(self, evidence: EvidenceLayer) -> dict[str, Any]:
        """高级视图：冻结的固定英文键（前端高级证据页直接依赖，见 API_SPEC §6.5）。

        - tool_results: 各 Tool 结果及可靠性（来自 tool_reliability）
        - heatmaps: 可疑区域热力图引用
        - source_metadata: 来源与元数据（C2PA/EXIF 等）
        - before_after_comparison: 前后画面条件差异
        - claim_evidence_mapping: 关键宣称与证据对应
        - decision_path: Agent 完整决策路径
        """
        return {
            "tool_results": [r.model_dump() for r in evidence.tool_reliability],
            "heatmaps": evidence.visual_evidence.raw.get("manipulation_map"),
            "source_metadata": evidence.source_evidence.raw,
            "before_after_comparison": [
                d for d in (evidence.before_after_evidence.raw.get("dimensions") or [])
            ],
            "claim_evidence_mapping": evidence.efficacy_evidence,
            "decision_path": evidence.agent_decision.decision_path if evidence.agent_decision else [],
        }

    # ------------------------------------------------------------------
    def _limitations(self, evidence: EvidenceLayer, label: FinalLabel) -> list[str]:
        limitations = ["Not detected 不等于一定没有，只表示当前证据中未检出"]
        if evidence.source_evidence.raw.get("c2pa", {}).get("status") in ("absent", "error"):
            limitations.append("未核验到 C2PA/来源信息，真实性无法确证（C2PA 缺失≠伪造）")
        if not evidence.before_after_evidence.raw:
            limitations.append("未提供 before/after 素材，妆效归因无法完整判断")
        if not evidence.efficacy_evidence:
            limitations.append("未检索到功效证据，宣称充分性存疑")
        if evidence.creator_submission.status != "done":
            limitations.append("创作者补证尚未提交/完成，结论可能随补证更新")
        return limitations

    # ------------------------------------------------------------------
    def _llm_enhance(self, evidence: EvidenceLayer, sections: list[TrustCardSection]) -> list[TrustCardSection] | None:
        """用 LLM 重写通俗解释区块（失败返回 None，由调用方保留模板）。"""
        try:
            system = (
                "你是 TrueGlow 映真的面向初学者的解释器。只基于给定证据组织解释，"
                "禁止编造证据，禁止输出没有依据的具体百分比。用简洁中文，面向美妆初学者。"
            )
            snapshot = {
                "final_label": evidence.agent_decision.final_label.value if evidence.agent_decision else "",
                "visual": evidence.visual_evidence.raw,
                "before_after": evidence.before_after_evidence.raw,
                "text_issues": [i.get("detail") for i in (evidence.text_evidence.raw.get("integrity_issues") or [])],
                "user_context": evidence.user_context,
            }
            text = self.provider.generate(system, json.dumps(snapshot, ensure_ascii=False))
            if not text.strip():
                return None
            # 用 LLM 输出替换前两个区块的内容（保持结构）
            lines = [ln.strip(" -0123456789.、") for ln in text.splitlines() if ln.strip()]
            if lines:
                sections[0].content = lines[:3]
            return sections
        except Exception:  # noqa: BLE001 - LLM 失败降级模板
            return None


reporter = ReportGenerator()
