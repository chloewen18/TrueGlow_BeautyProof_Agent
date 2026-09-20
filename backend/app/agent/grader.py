"""风险分级：把融合后的证据层转化为四级结论与三维风险判断。

结论分级（方案文档第七节）：
  verified                  已验证
  partially_suspicious      部分可疑
  insufficient_evidence     证据不足
  high_risk_misleading      高风险误导

规则要点：
  - 不因"无 C2PA"判伪造；来源 Unknown 时无法达到 verified
  - 检测结果必须结合可靠性（Low reliability 的证据不单独定罪）
  - high_risk_misleading 需要"多种证据相互印证 + 影响核心功效宣称"
  - 关键证据缺失时倾向 insufficient_evidence，不做二元判假
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..schemas.common import EvidenceReliability, FinalLabel
from ..schemas.evidence import AgentDecision, EvidenceLayer
from ..schemas.tools import ImageForensicsEvidence, SourceTraceEvidence

RISK_HIGH = "High"
RISK_MEDIUM = "Medium"
RISK_LOW = "Low"


@dataclass
class RiskProfile:
    content_integrity: str = RISK_LOW      # 内容完整性风险
    attribution: str = RISK_LOW            # 妆效归因可靠性（高=归因越不可靠）
    claim_sufficiency: str = RISK_LOW      # 宣称证据充分性
    confidence: str = "Medium"             # 结论置信度 High/Medium/Low
    source_unknown: bool = False           # 来源状态 Unknown（C2PA 缺失且无补证）
    reasons: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    affected_claims: list[str] = field(default_factory=list)
    decision_path: list[str] = field(default_factory=list)


class RiskGrader:
    """规则驱动风险分级（大模型只负责组织解释，不替代规则）。"""

    def grade(self, layer: EvidenceLayer) -> AgentDecision:
        profile = self._profile(layer)
        final = self._final_label(profile)

        return AgentDecision(
            final_label=final,
            content_integrity_risk=self._dim_text("内容完整性", profile.content_integrity, "素材是否被加工/拼接/伪造"),
            attribution_reliability=self._dim_text("妆效归因可靠性", profile.attribution, "效果能否合理归因于产品"),
            claim_evidence_sufficiency=self._dim_text("宣称证据充分性", profile.claim_sufficiency, "文案是否得到可信证据支持"),
            personal_fit_hint=self._fit_hint(layer),
            confidence=self._confidence_text(profile),
            decision_path=profile.decision_path,
            affected_claims=profile.affected_claims,
        )

    # ------------------------------------------------------------------
    def _profile(self, layer: EvidenceLayer) -> RiskProfile:
        p = RiskProfile()
        path = p.decision_path
        path.append(f"evidence_fusion: 来源{len(layer.source_evidence.items)}条 / 视觉{len(layer.visual_evidence.items)}条 / 前后对比{len(layer.before_after_evidence.items)}条 / 文本{len(layer.text_evidence.items)}条")

        # ---- 维度 1：内容完整性 ----
        src = SourceTraceEvidence(**layer.source_evidence.raw) if layer.source_evidence.raw else None
        vis = ImageForensicsEvidence(**layer.visual_evidence.raw) if layer.visual_evidence.raw else None

        # 来源状态：C2PA 缺失/错误 且 无创作者补证 → Unknown（不判伪造，但无法确证真实性）
        if src and src.c2pa.status in ("absent", "error") and layer.creator_submission.status != "done":
            p.source_unknown = True
            path.append("rule: c2pa=absent/error 且无补证 -> source_unknown=True")

        if src and src.c2pa.status == "invalid":
            p.content_integrity = RISK_HIGH
            p.reasons.append("C2PA 签名验证失败（来源不可信）")
            path.append("rule: c2pa=invalid -> content_integrity=High")
        elif vis:
            hard_forge = (
                vis.local_replacement.value != "Not detected"
                or vis.splicing.value != "Not detected"
                or vis.inpainting.value != "Not detected"
            )
            if hard_forge and vis.reliability.value in ("Medium", "High"):
                p.content_integrity = RISK_HIGH
                p.reasons.append("检出局部替换/拼接/inpainting 且可靠性达标")
                path.append("rule: 硬篡改检出+可靠性达标 -> content_integrity=High")
            elif vis.skin_smoothing.value == "High" or vis.ai_generated.value == "Detected":
                p.content_integrity = RISK_MEDIUM
                p.reasons.append("较强平滑处理或 AI 生成痕迹，需结合可靠性综合判断")
                path.append("rule: smoothing=High/ai=Detected -> content_integrity=Medium")
                # 交叉印证：平滑处理 + 文案宣称"原相机/零滤镜" → 多种证据相互印证，升为 High
                t5_raw = layer.text_evidence.raw
                if t5_raw:
                    from ..schemas.tools import TextIntegrityEvidence

                    te = TextIntegrityEvidence(**t5_raw)
                    contrad = any(
                        ("原相机" in (i.detail or "")) or ("零滤镜" in (i.detail or ""))
                        for i in te.integrity_issues
                    )
                    if contrad and vis.reliability.value in ("Medium", "High"):
                        p.content_integrity = RISK_HIGH
                        p.reasons.append("平滑处理与「原相机/零滤镜」宣称相互印证，直接影响核心功效表达")
                        path.append("rule: smoothing=High + 文案矛盾相互印证 -> content_integrity=High")
            elif src and src.metadata_anomalies:
                p.content_integrity = RISK_MEDIUM
                p.reasons.append("存在元数据异常")
                path.append("rule: 元数据异常 -> content_integrity=Medium")
            else:
                path.append("rule: 无硬篡改证据 -> content_integrity=Low")
        else:
            p.limitations.append("缺少来源与视觉证据，内容完整性无法确认")

        # ---- 维度 2：妆效归因可靠性 ----
        ba = layer.before_after_evidence.raw
        if ba:
            from ..schemas.tools import BeforeAfterEvidence

            be = BeforeAfterEvidence(**ba)
            reliability = be.comparison_reliability.value
            # 归因强度 Unknown = 未计算或证据不足。按项目原则应落在「存疑」而非「高风险误导」，
            # 也不能因为它不是 Low/Medium 就掉进「可比较、归因可靠」。
            if be.attribution_strength.value == "Unknown":
                p.attribution = RISK_MEDIUM
                p.limitations.append("前后对比未产生有效计算结果，妆效归因无法判断（不等于可归因于产品）")
                path.append("rule: attribution_strength=Unknown -> attribution=Medium(存疑)")
            elif reliability == "Low":
                p.attribution = RISK_HIGH
                p.reasons.append("前后对比条件差异显著，效果归因不可靠")
                path.append("rule: comparison_reliability=Low -> attribution=High")
            elif reliability == "Medium":
                p.attribution = RISK_MEDIUM
                p.reasons.append("前后对比条件存在部分差异")
                path.append("rule: comparison_reliability=Medium -> attribution=Medium")
            elif reliability == "High":
                p.attribution = RISK_LOW
                path.append("rule: comparison_reliability=High -> attribution=Low")
            else:
                # 枚举未来新增取值时不得落入默认的「可比较/可靠」分支，一律保守处理
                p.attribution = RISK_MEDIUM
                p.limitations.append(f"前后对比可靠性取值无法识别（{reliability}），按存疑处理")
                path.append("rule: comparison_reliability 取值未知 -> attribution=Medium(存疑)")
        else:
            p.attribution = RISK_MEDIUM  # 缺失按中等风险处理并提示
            p.limitations.append("未提供 before/after 素材，妆效归因无法完整判断")
            path.append("rule: before_after 缺失 -> attribution=Medium(存疑)")

        # ---- 维度 3：宣称证据充分性 ----
        t5 = layer.text_evidence.raw
        if t5:
            from ..schemas.tools import TextIntegrityEvidence

            te = TextIntegrityEvidence(**t5)
            severe_issues = [i for i in te.integrity_issues if i.severity.value == "High"]
            unsupported = [e for e in te.efficacy_evidence if not e.matched]
            strong_claims = [c for c in te.claims if c.severity.value == "High"]
            if severe_issues:
                p.claim_sufficiency = RISK_HIGH
                p.reasons.append(f"文本完整性高风险问题：{len(severe_issues)} 项")
                p.affected_claims.extend(i.detail for i in severe_issues)
                path.append("rule: 文本高风险问题 -> claim_sufficiency=High")
            elif unsupported and strong_claims:
                p.claim_sufficiency = RISK_MEDIUM
                p.reasons.append(f"{len(strong_claims)} 项量化/强宣称未找到官方功效证据支持")
                p.affected_claims.extend(e.text for e in strong_claims[:5])
                path.append("rule: 强宣称无证据支持 -> claim_sufficiency=Medium")
            elif te.disclosure == "not_found" and strong_claims:
                p.claim_sufficiency = RISK_MEDIUM
                p.reasons.append("存在量化/强宣称但未发现商业合作或 AI 使用声明")
                path.append("rule: 强宣称+disclosure=not_found -> claim_sufficiency=Medium")
            else:
                if te.disclosure == "not_found" and te.claims:
                    p.limitations.append("未发现商业合作/AI 使用声明（无强宣称，仅提示）")
                path.append("rule: 文本无重大问题 -> claim_sufficiency=Low")
        else:
            p.claim_sufficiency = RISK_MEDIUM
            p.limitations.append("缺少文本证据，宣称充分性无法判断")

        # ---- 置信度 ----
        reliabilities = [r.reliability.value for r in layer.tool_reliability if r.status == "success"]
        low_cnt = reliabilities.count("Low")
        missing = [r for r in layer.tool_reliability if r.status == "missing"]
        if low_cnt >= 2 or len(missing) >= 2:
            p.confidence = "Low"
        elif low_cnt == 1 or len(missing) == 1:
            p.confidence = "Medium"
        else:
            p.confidence = "High"
        path.append(f"rule: 置信度={p.confidence}（低可靠证据{low_cnt}条，缺失{len(missing)}个维度）")
        return p

    # ------------------------------------------------------------------
    def _final_label(self, p: RiskProfile) -> FinalLabel:
        # 高风险误导：多种证据相互印证 + 影响核心功效表达
        if p.content_integrity == RISK_HIGH and (p.attribution == RISK_HIGH or p.claim_sufficiency == RISK_HIGH):
            p.decision_path.append("rule: content=High 且 (attribution=High 或 claim=High) -> high_risk_misleading")
            return FinalLabel.HIGH_RISK_MISLEADING
        # 来源完全 Unknown 且无其他风险 → 证据不足（不做二元判假；来源缺失无法达到 verified）
        if p.content_integrity == RISK_LOW and p.attribution == RISK_LOW and p.claim_sufficiency == RISK_LOW:
            if p.source_unknown:
                p.decision_path.append("rule: 三维度均 Low 但来源 Unknown -> insufficient_evidence（无法确证真实性）")
                return FinalLabel.INSUFFICIENT_EVIDENCE
            p.decision_path.append("rule: 三维度均 Low 且来源可验证 -> verified")
            return FinalLabel.VERIFIED
        # 存在可疑但并非全部不可信 → 部分可疑
        if p.content_integrity in (RISK_MEDIUM, RISK_HIGH) or p.attribution in (RISK_MEDIUM, RISK_HIGH) or p.claim_sufficiency in (RISK_MEDIUM, RISK_HIGH):
            # 但若只是"证据缺失"导致的 Medium，降为证据不足
            missing_only = not p.reasons and (p.attribution == RISK_MEDIUM or p.claim_sufficiency == RISK_MEDIUM)
            if missing_only:
                p.decision_path.append("rule: 风险由证据缺失引起且无实际可疑证据 -> insufficient_evidence")
                return FinalLabel.INSUFFICIENT_EVIDENCE
            p.decision_path.append("rule: 存在可疑证据但非全部不可信 -> partially_suspicious")
            return FinalLabel.PARTIALLY_SUSPICIOUS
        p.decision_path.append("rule: 兜底 -> insufficient_evidence")
        return FinalLabel.INSUFFICIENT_EVIDENCE

    # ------------------------------------------------------------------
    @staticmethod
    def _dim_text(name: str, level: str, what: str) -> str:
        return f"{name}: {level}（{what}）"

    @staticmethod
    def _confidence_text(p: RiskProfile) -> str:
        return f"置信度 {p.confidence}；系统看到的证据与局限：{'；'.join(p.limitations) if p.limitations else '证据覆盖较完整'}"

    @staticmethod
    def _fit_hint(layer: EvidenceLayer) -> str:
        ctx = layer.user_context or {}
        skin = ctx.get("skin_type")
        concerns = ctx.get("concerns")
        if skin:
            base = f"产品是否适合{skin}肤质需结合个人试用，系统无法仅凭内容判断适配度"
            if concerns:
                base += f"，建议重点观察{concerns}相关表现"
            return base
        return "个人适配度需结合肤质与关注点进一步判断（可补充肤质信息）"


grader = RiskGrader()
