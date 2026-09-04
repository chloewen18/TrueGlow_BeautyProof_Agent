"""TrueGlow 公共 schema：统一信封、分级枚举、错误结构。

接口规范详见 docs/API_SPEC.md（v1.0，冻结目标 2026-09-06）。
所有 Tool 与 Main Agent API 都使用统一 Envelope。
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


# ---------------------------------------------------------------------------
# 分级枚举（避免伪精确数字，见方案文档第六节）
# ---------------------------------------------------------------------------
class Severity(str, Enum):
    """强度/风险分级：Low / Medium / High。"""

    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class Strength(str, Enum):
    """归因/证据强度：Weak / Moderate / Strong。"""

    WEAK = "Weak"
    MODERATE = "Moderate"
    STRONG = "Strong"


class ComparisonLevel(str, Enum):
    """前后对比维度差异：Similar / Different / Significant difference。"""

    SIMILAR = "Similar"
    DIFFERENT = "Different"
    SIGNIFICANT_DIFFERENCE = "Significant difference"


class DetectStatus(str, Enum):
    """篡改/修饰检测状态。Not detected 不等于"一定没有"，只表示当前证据中未检出。"""

    NOT_DETECTED = "Not detected"
    DETECTED = "Detected"
    UNKNOWN = "Unknown"


class EvidenceReliability(str, Enum):
    """证据可靠性分级（必须与结论一起看）。"""

    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class FinalLabel(str, Enum):
    """最终四级结论（见方案文档第七节）。"""

    VERIFIED = "verified"
    PARTIALLY_SUSPICIOUS = "partially_suspicious"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    HIGH_RISK_MISLEADING = "high_risk_misleading"


# ---------------------------------------------------------------------------
# 统一信封
# ---------------------------------------------------------------------------
class ToolRequest(BaseModel):
    """统一 Tool 请求信封。payload 的具体结构由各 Tool 定义。"""

    tool: str = Field(..., description="Tool 标识，如 source_trace")
    request_id: str = Field(..., description="调用方生成的全链路追踪 ID，可复用上游 request_id")
    payload: dict[str, Any] = Field(..., description="各 Tool 定义的请求参数，见 docs/API_SPEC.md 各节")
    options: dict[str, Any] = Field(default_factory=dict, description="可选参数（超时、语言、调试开关等）")


class ToolMeta(BaseModel):
    """响应元信息，保证可追溯。"""

    version: str = Field(default="1.0.0", description="接口规范版本")
    model: str = Field(default="mock", description="实际执行的模型/规则版本，便于追踪")
    latency_ms: int = Field(0, description="Tool 处理耗时（毫秒）")
    warnings: list[str] = Field(default_factory=list, description="非致命警告，如证据缺失说明")


class ToolError(BaseModel):
    """错误结构。错误码定义见 docs/API_SPEC.md 附录。"""

    code: str = Field(..., description="错误码，如 TOOL_NOT_FOUND")
    message: str = Field(..., description="人类可读错误信息")
    details: Optional[dict[str, Any]] = Field(None, description="附加详情（可选）")


class ToolResponse(BaseModel):
    """统一 Tool 响应信封。"""

    tool: str = Field(..., description="Tool 标识")
    request_id: str = Field(..., description="与请求一致的 request_id")
    status: Literal["success", "error", "partial"] = Field(
        "success", description="success=完成; partial=部分证据可用（其余缺失/低可靠）; error=失败"
    )
    evidence: dict[str, Any] = Field(default_factory=dict, description="结构化证据，schema 见各 Tool 定义")
    meta: ToolMeta = Field(default_factory=ToolMeta)
    error: Optional[ToolError] = Field(None, description="status=error 时的错误信息")


class ApiResponse(BaseModel):
    """Main Agent 编排 API 的统一响应信封（/api/v1/verify 等）。"""

    request_id: str
    status: Literal["success", "error", "partial"]
    result: dict[str, Any] = Field(default_factory=dict, description="各端点定义的业务结果（报告/计划/分级等）")
    meta: ToolMeta = Field(default_factory=ToolMeta)
    error: Optional[ToolError] = Field(None)


# ---------------------------------------------------------------------------
# 证据层通用结构
# ---------------------------------------------------------------------------
class EvidenceItem(BaseModel):
    """单条证据：来源 Tool、可解释依据、可靠性、是否影响结论。"""

    evidence_id: str = Field(..., description="证据唯一 ID，形如 src-001")
    tool: str = Field(..., description="产生该证据的 Tool 标识")
    claim: str = Field(..., description="证据声称的内容（人类可读）")
    finding: dict[str, Any] = Field(default_factory=dict, description="结构化发现（数值/分级/位置等）")
    reliability: EvidenceReliability = Field(EvidenceReliability.MEDIUM, description="该证据可靠性")
    source: Optional[str] = Field(None, description="证据来源说明，如 'EXIF 元数据' / 'TruFor inference'")
    confidence_note: Optional[str] = Field(None, description="对局限性的说明，如 '平台压缩可能影响判断'")


class ToolReliabilityMap(BaseModel):
    """各 Tool 结果的可靠性汇总，用于冲突处理。"""

    tool: str
    status: str = "success"
    reliability: EvidenceReliability = EvidenceReliability.MEDIUM
    note: Optional[str] = None
