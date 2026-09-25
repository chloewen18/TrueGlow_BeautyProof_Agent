"""5 个专业 Tool 的请求 payload 与证据（响应 payload）schema。

对应方案文档第六节：
  T1 page_understanding  页面理解与任务拆解
  T2 source_trace        来源溯源与创作者证明
  T3 image_forensics     图像鉴伪与底妆修饰检测
  T4 before_after        前后对比一致性与妆效归因
  T5 text_integrity      文本完整性、功效证据与用户解释

说明：Tool 响应信封中的 evidence 字段即下列 Evidence 模型的 dict 形式。
所有分级字段只允许 Low/Medium/High 或 Weak/Moderate/Strong，禁止伪精确百分比。
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from .common import (
    ComparisonLevel,
    DetectStatus,
    EvidenceReliability,
    Severity,
    Strength,
)


class ComputedEvidence(BaseModel):
    model_config = {"extra": "allow"}
    provenance: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# T1 页面理解与任务拆解
# ---------------------------------------------------------------------------
class MediaRef(BaseModel):
    """媒体引用：Mock 阶段用 url/本地路径/说明文字代替真实文件。"""

    kind: Literal["image", "video_frame", "video", "text", "audio"] = "image"
    ref: str = Field(..., description="URL / 本地路径 / 说明文字")
    note: Optional[str] = None


class PageUnderstandingRequest(BaseModel):
    """输入：用户正在浏览的内容。"""

    url: Optional[str] = None
    title: Optional[str] = None
    body_text: Optional[str] = None
    media: list[MediaRef] = Field(default_factory=list, description="页面中的图片/视频帧")
    user_context: dict[str, Any] = Field(
        default_factory=dict,
        description="用户需求：skin_type(干皮/油皮/混合皮)、concerns(遮瑕/服帖/控油/持妆)、goal(核验可信度/判断适配度)",
    )


class PageUnderstandingEvidence(ComputedEvidence):
    """输出：可分析对象 + 待核验任务清单。"""

    content_type: str = Field(..., description="如 foundation_before_after_review / unboxing / single_try_on")
    product: Optional[str] = Field(None, description="识别出的产品")
    claims: list[str] = Field(default_factory=list, description="提取的功效宣称，如 ['隐形毛孔','持妆12小时']")
    media_tasks: list[str] = Field(
        default_factory=list, description="建议核验任务，如 before_after_consistency / skin_smoothing / texture_analysis"
    )
    disclosure: Literal["found", "not_found", "unknown"] = "unknown"
    media: list[MediaRef] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list, description="其他值得核验的点，如 '12小时持妆缺少长时段证据'")


# ---------------------------------------------------------------------------
# T2 来源溯源与创作者证明
# ---------------------------------------------------------------------------
class C2paInfo(BaseModel):
    """C2PA / Content Credentials 状态。

    present = 检测到清单标记（仅存在性检测，未验证签名链）；
    valid   = 存在且签名链验证通过（当前未实现，预留）。
    """

    status: Literal["valid", "invalid", "present", "absent", "error"] = "absent"
    detail: Optional[str] = None


class SourceTraceRequest(BaseModel):
    """输入：文件或媒体引用 + 可选创作者补证材料。"""

    files: list[MediaRef] = Field(default_factory=list, description="待溯源文件")
    creator_submission: Optional[dict[str, Any]] = Field(
        None, description="创作者补交材料：original_file、filter_params、shooting_params、retest_clip 等"
    )


class SourceTraceEvidence(ComputedEvidence):
    """输出：来源信息 + 元数据异常 + 文件基础信息。"""

    c2pa: C2paInfo = Field(default_factory=C2paInfo)
    exif: dict[str, Any] = Field(default_factory=dict, description="EXIF/XMP 摘要：device、create_time、software 等")
    metadata_complete: bool = Field(True, description="元数据是否完整（False=可能受平台压缩/转码影响）")
    metadata_anomalies: list[str] = Field(default_factory=list, description="元数据矛盾/异常列表")
    ai_declared: Optional[bool] = Field(None, description="是否声明使用生成式 AI 或后期编辑")
    file_info: dict[str, Any] = Field(default_factory=dict, description="哈希、格式、尺寸、大小")
    creator_submission_status: Literal["none", "received", "processing", "done"] = "none"
    conclusion: str = Field(..., description="结论：如 'C2PA 存在且验证通过，来源证据可靠' 或 'C2PA 不存在，来源状态 Unknown'")


# ---------------------------------------------------------------------------
# T3 图像鉴伪与底妆修饰检测
# ---------------------------------------------------------------------------
class ImageForensicsRequest(BaseModel):
    """输入：单张或多张图片。"""

    images: list[MediaRef] = Field(default_factory=list)
    task: Literal["forensics", "retouching", "both"] = "both"


class ManipulationMapRef(BaseModel):
    """像素级可疑区域图引用。Mock 阶段返回说明文字；真实实现返回热力图路径/Base64。"""

    kind: Literal["path", "base64", "description"] = "description"
    value: str = Field(..., description="热力图引用或说明")


class ImageForensicsEvidence(ComputedEvidence):
    """输出：通用鉴伪 + 底妆专项。"""

    integrity_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="1-TruFor可疑分数；失败时为空")
    manipulation_map: Optional[ManipulationMapRef] = Field(None, description="像素级可疑区域图")
    reliability_map: Optional[ManipulationMapRef] = Field(None, description="可靠性图")
    local_replacement: DetectStatus = DetectStatus.NOT_DETECTED
    splicing: DetectStatus = DetectStatus.NOT_DETECTED
    inpainting: DetectStatus = DetectStatus.NOT_DETECTED
    ai_generated: DetectStatus = DetectStatus.UNKNOWN
    skin_smoothing: Severity = Severity.LOW
    texture_loss: Severity = Severity.LOW
    whitening: Severity = Severity.LOW
    face_reshape: Severity = Severity.LOW
    exposure_shift: Severity = Severity.LOW
    reliability: EvidenceReliability = EvidenceReliability.MEDIUM
    notes: list[str] = Field(default_factory=list, description="解释性说明，如 '平滑处理可能遮盖卡粉/纹理'")


# ---------------------------------------------------------------------------
# T4 前后对比一致性与妆效归因
# ---------------------------------------------------------------------------
class BeforeAfterRequest(BaseModel):
    """输入：Before / After 一对图片。"""

    before: MediaRef
    after: MediaRef
    claimed_effect: Optional[str] = Field(None, description="内容宣称的效果，如 '隐形毛孔'")


class ConsistencyDimension(BaseModel):
    """单个对比维度。"""

    dimension: str = Field(..., description="如 face_angle / crop / exposure / white_balance / skin_texture / smoothing")
    level: ComparisonLevel
    detail: str = Field(..., description="如 'After +24% 曝光' / 'After 平滑强于 Before'")


class BeforeAfterEvidence(ComputedEvidence):
    """输出：可比较性 + 归因提示。"""

    dimensions: list[ConsistencyDimension] = Field(default_factory=list)
    comparison_reliability: EvidenceReliability = Field(EvidenceReliability.LOW)
    attribution_summary: str = Field(
        ..., description="归因结论，如 'After 图存在明显曝光变化和皮肤纹理平滑，毛孔减少不能完全归因于产品'"
    )
    attribution_strength: Strength = Strength.WEAK
    suggested_viewer_actions: list[str] = Field(default_factory=list, description="建议消费者参考的信息")


# ---------------------------------------------------------------------------
# T5 文本完整性、功效证据与用户解释
# ---------------------------------------------------------------------------
class Claim(BaseModel):
    """提取出的宣称。"""

    text: str = Field(..., description="宣称原文")
    kind: Literal["efficacy", "factual", "quantified", "comparative", "other"] = "efficacy"
    severity: Severity = Severity.LOW
    evidence_supported: Optional[bool] = Field(None, description="是否找到功效证据支持（None=未检索）")


class IntegrityIssue(BaseModel):
    """文本完整性问题。"""

    type: str = Field(..., description="contradiction / exaggerated_quantified / abnormal_repetition / missing_disclosure / beyond_evidence")
    severity: Severity = Severity.LOW
    detail: str


class EfficacyEvidence(BaseModel):
    """功效证据检索结果（对应方案文档功效证据库结构）。"""

    product: str
    evidence_level_original: Optional[str] = None
    limitations: list[str] = Field(default_factory=list)
    source_verification: str = "delivery_library_not_online_verified"
    claim: str
    claim_type: str = Field(..., description="如 抗皱/紧致/舒缓/控油/遮瑕/持妆")
    evidence_method: Optional[str] = None
    evaluation_duration: Optional[str] = None
    quantified_result: Optional[str] = None
    official_source: Optional[str] = None
    evidence_level: Strength = Strength.WEAK
    matched: bool = Field(False, description="是否命中官方/可信证据")


class TextIntegrityRequest(BaseModel):
    """输入：正文/OCR 文本 + 用户上下文。"""

    text: Optional[str] = None
    ocr_text: Optional[str] = None
    comments: list[str] = Field(default_factory=list, description="评论区文本（首版仅异常模式提示）")
    user_context: dict[str, Any] = Field(default_factory=dict)


class TextIntegrityEvidence(ComputedEvidence):
    """输出：文本完整性 + 功效证据 + 用户解释。"""

    claims: list[Claim] = Field(default_factory=list)
    member4_analysis: dict[str, Any] = Field(default_factory=dict)
    integrity_issues: list[IntegrityIssue] = Field(default_factory=list)
    disclosure: Literal["found", "not_found", "unknown"] = "unknown"
    efficacy_evidence: list[EfficacyEvidence] = Field(default_factory=list)
    user_explanation: str = Field(..., description="面向初学者的通俗解释，把风险连接到底妆实际问题")
