"""最终报告 schema：full_report（完整核验报告）+ trust_card（Beauty Trust Card）。

对应方案文档第八节（Beauty Trust Card）与第十节（结构化证据层）。
机器可读版本见 schemas/report.schema.json / trust_card.schema.json。
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from .common import FinalLabel
from .evidence import EvidenceLayer


class TrustCardSection(BaseModel):
    """信任卡的一个区块。"""

    title: str = Field(..., description="如 主要发现 / 这会怎样影响你 / 哪些信息仍可参考")
    content: list[str] = Field(default_factory=list, description="要点列表（面向初学者，通俗）")
    details: Optional[dict[str, Any]] = Field(None, description="高级用户可展开的细节（可选）")


class TrustCard(BaseModel):
    """Beauty Trust Card：消费者端一目了然的信任卡片。"""

    request_id: str
    content_id: str
    verdict: FinalLabel
    verdict_label: str = Field(..., description="中文结论，如 部分可疑")
    product: Optional[str] = None
    main_findings: list[str] = Field(default_factory=list, description="主要发现（对应方案文档示例 1/2/3）")
    sections: list[TrustCardSection] = Field(default_factory=list)
    creator_actions: list[str] = Field(default_factory=list, description="创作者可补充的材料")
    advanced: dict[str, Any] = Field(
        default_factory=dict,
        description="高级视图：热力图引用、来源元数据、前后条件差异、宣称-证据对应、各 Tool 结果与可靠性、Agent 决策路径",
    )
    generated_at: str = ""


class FullReport(BaseModel):
    """完整核验报告：证据链 + 决策 + 卡片，供平台审核与高级用户查看。"""

    report_id: str
    request_id: str
    content_id: str
    schema_version: str = "1.0.0"
    evidence: EvidenceLayer
    trust_card: TrustCard
    tool_calls: list[dict[str, Any]] = Field(default_factory=list, description="每次 Tool 调用的记录（耗时/状态/证据）")
    limitations: list[str] = Field(default_factory=list, description="系统局限与未核验范围")
