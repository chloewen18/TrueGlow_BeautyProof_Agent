"""结构化证据层 schema：单条内容的完整证据结构（对应方案文档 10.1）。"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from .common import EvidenceItem, FinalLabel, ToolReliabilityMap


class AgentDecision(BaseModel):
    """Main Agent 的决策记录：结论 + 风险维度 + 决策路径。"""

    final_label: FinalLabel
    content_integrity_risk: str = Field(..., description="内容完整性风险：素材是否被加工/拼接/伪造")
    attribution_reliability: str = Field(..., description="妆效归因可靠性：效果能否合理归因于产品")
    claim_evidence_sufficiency: str = Field(..., description="宣称证据充分性：文案是否得到可信证据支持")
    personal_fit_hint: Optional[str] = Field(None, description="个人适配提示：产品是否可能符合当前用户需求")
    confidence: str = Field(..., description="结论置信度与局限：系统看到了什么、没有看到什么")
    decision_path: list[str] = Field(default_factory=list, description="完整决策路径（可追溯）")
    affected_claims: list[str] = Field(default_factory=list, description="受影响/存疑的功效宣称")


class SourceEvidenceLayer(BaseModel):
    """来源证据（T2 产出）。"""

    summary: str = ""
    items: list[EvidenceItem] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class VisualEvidenceLayer(BaseModel):
    """视觉证据（T3 产出）。"""

    summary: str = ""
    items: list[EvidenceItem] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class BeforeAfterEvidenceLayer(BaseModel):
    """前后对比证据（T4 产出）。"""

    summary: str = ""
    items: list[EvidenceItem] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class TextEvidenceLayer(BaseModel):
    """文本与功效证据（T5 产出）。"""

    summary: str = ""
    items: list[EvidenceItem] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class CreatorSubmission(BaseModel):
    """创作者补证材料与复核状态。"""

    status: Literal["none", "received", "processing", "done"] = "none"
    materials: dict[str, Any] = Field(default_factory=dict, description="原始素材/滤镜参数/拍摄参数/复测片段等")
    review_result: Optional[str] = Field(None, description="复核后结论变化说明")
    credential: Optional[dict[str, Any]] = Field(None, description="可信妆效凭证：验证范围、日期")


class HumanReview(BaseModel):
    """人工复核（阶段 2+ 使用）。"""

    status: Literal["none", "pending", "approved", "rejected"] = "none"
    reviewer: Optional[str] = None
    note: Optional[str] = None


class EvidenceLayer(BaseModel):
    """单条内容的结构化证据层（对应方案文档 10.1 的 evidence 结构）。"""

    content_id: str
    source_evidence: SourceEvidenceLayer = Field(default_factory=SourceEvidenceLayer)
    visual_evidence: VisualEvidenceLayer = Field(default_factory=VisualEvidenceLayer)
    before_after_evidence: BeforeAfterEvidenceLayer = Field(default_factory=BeforeAfterEvidenceLayer)
    text_evidence: TextEvidenceLayer = Field(default_factory=TextEvidenceLayer)
    efficacy_evidence: list[dict[str, Any]] = Field(default_factory=list)
    user_context: dict[str, Any] = Field(default_factory=dict)
    tool_reliability: list[ToolReliabilityMap] = Field(default_factory=list)
    agent_decision: Optional[AgentDecision] = Field(None)
    creator_submission: CreatorSubmission = Field(default_factory=CreatorSubmission)
    human_review: HumanReview = Field(default_factory=HumanReview)
    final_label: FinalLabel = FinalLabel.INSUFFICIENT_EVIDENCE
