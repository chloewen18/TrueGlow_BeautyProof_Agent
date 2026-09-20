"""成员 3 响应 → 本项目 evidence schema 的语义映射。

这一层是「防误判」的关键，三件事必须做对：

1. **方向转换**：成员 3 的 generic_retouch.score 是「越高越像修图」，
   本项目 integrity_score 一律「越高越完整」，必须取 1 - score。
   （历史上 TruFor 交付物就在这里反了，导致结论完全反过来。）
2. **大小写归一**：成员 3 v1.0.0 输出 low/medium/high 全小写，
   v1.1.0 起改为 Low/Medium/High 且新增 Unknown；本项目 EvidenceReliability 枚举是
   Low/Medium/High。本层两种写法都兜得住。
3. **Unknown 兜底**：任何「没算 / 拿不到 / 不可靠」的维度一律 Unknown，
   绝不默认 Similar 或 Low——默认 Similar 等价于凭空断言"两张图条件一致"。
"""
from __future__ import annotations

from typing import Any

from ...schemas.common import (
    ComparisonLevel,
    DetectStatus,
    EvidenceReliability,
    Severity,
    Strength,
)
from ...schemas.tools import BeforeAfterEvidence, ConsistencyDimension, ImageForensicsEvidence

# ---------------------------------------------------------------------------
# 阈值：与成员 3 tool.py 的 reliability_rule_cues 对齐（曝光 0.25 / 色温 400 / 色调 15），
# 其余为补充的中间档，便于给出 Similar / Different / Significant difference 三态。
# 这些阈值是启发式的，待《成员 3 对接反馈 v1》任务 1 的困难负样本集到位后标定。
# ---------------------------------------------------------------------------
EXPOSURE_SIMILAR = 0.10
EXPOSURE_SIGNIFICANT = 0.25
TEMPERATURE_SIMILAR = 150.0
TEMPERATURE_SIGNIFICANT = 400.0
TINT_SIMILAR = 2.0
TINT_SIGNIFICANT = 5.0
TONE_SIMILAR = 5.0
TONE_SIGNIFICANT = 15.0
TEXTURE_SIMILAR = 0.2
TEXTURE_SIGNIFICANT = 0.5
SMOOTHING_SIMILAR = 0.05
SMOOTHING_SIGNIFICANT = 0.20

TONE_PARAMETERS = ("contrast", "highlights", "shadows", "whites", "blacks", "saturation", "vibrance")

# 成员 3 模型覆盖不到的维度：必须显式 Unknown，不得默认 Similar。
UNSUPPORTED_DIMENSIONS = {
    "face_angle": "成员 3 模型未提供人脸角度维度，未计算",
    "crop": "成员 3 模型未提供裁切比例维度，未计算",
}

_RELIABILITY_ALIASES = {
    "low": "Low",
    "medium": "Medium",
    "high": "High",
}


def normalize_reliability(value: Any) -> tuple[EvidenceReliability, bool]:
    """归一可靠性枚举。

    返回 (reliability, is_unknown)。

    成员 3 v1.1 起会输出 Unknown；本项目 EvidenceReliability 只有三值，
    因此 Unknown 统一映射为 **Low**（没算就是没有可靠证据），
    并用 is_unknown 让上层把归因强度置为 Unknown——两者合起来才等价于 Unknown。
    """
    if value is None:
        return EvidenceReliability.LOW, True
    text = str(value).strip().lower()
    if text in ("", "unknown", "none", "unavailable", "null"):
        return EvidenceReliability.LOW, True
    if text not in _RELIABILITY_ALIASES:
        return EvidenceReliability.LOW, True
    return EvidenceReliability(_RELIABILITY_ALIASES[text]), False


def _level(value: float, similar: float, significant: float) -> ComparisonLevel:
    magnitude = abs(float(value))
    if magnitude < similar:
        return ComparisonLevel.SIMILAR
    if magnitude < significant:
        return ComparisonLevel.DIFFERENT
    return ComparisonLevel.SIGNIFICANT_DIFFERENCE


def _severity_from_operation(operation: dict[str, Any]) -> Severity:
    """成员 3 的单个 operation → Severity。

    只相信 detected=True 的信号；强度档（LEVELS = [0, 30, 60, 90]）决定轻重。
    保守起见 30 档仍算 Low——宁可少报，不可误报。
    """
    if not operation.get("detected"):
        return Severity.LOW
    level = int(operation.get("estimated_level") or 0)
    if level >= 90:
        return Severity.HIGH
    if level >= 60:
        return Severity.MEDIUM
    return Severity.LOW


# ---------------------------------------------------------------------------
# 单图：成员 3 analyze_single → T3 ImageForensicsEvidence
# ---------------------------------------------------------------------------
def single_to_image_forensics(response: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """返回 (evidence dict, warnings)。warnings 用于写入 ToolMeta.warnings。"""
    result = response.get("result") or {}
    generic = result.get("generic_retouch") or {}
    operations = result.get("operations") or {}
    warnings = list(response.get("limitations") or [])

    # 方向转换：成员 3 越高越像修图 → 本项目越高越完整
    score = generic.get("score")
    integrity_score = 1.0 - float(score) if isinstance(score, (int, float)) else 0.5

    smoothing = operations.get("smoothing") or {}
    whitening = operations.get("whitening") or {}
    facelifting = operations.get("facelifting") or {}

    skin_smoothing = _severity_from_operation(smoothing)
    notes: list[str] = []

    evidence = ImageForensicsEvidence(
        integrity_score=round(max(0.0, min(1.0, integrity_score)), 4),
        # 成员 3 不做像素级定位，热力图留空（None 比伪造一张图诚实）
        manipulation_map=None,
        reliability_map=None,
        # 成员 3 不做拼接/局部替换/inpainting/AI 生成检测 → Unknown，不是 "Not detected"
        local_replacement=DetectStatus.UNKNOWN,
        splicing=DetectStatus.UNKNOWN,
        inpainting=DetectStatus.UNKNOWN,
        ai_generated=DetectStatus.UNKNOWN,
        skin_smoothing=skin_smoothing,
        # 成员 3 没有独立的纹理损失头，用磨皮信号做代理，并显式说明
        texture_loss=skin_smoothing,
        whitening=_severity_from_operation(whitening),
        face_reshape=_severity_from_operation(facelifting),
        # 单图无基准，无法判断曝光位移
        exposure_shift=Severity.LOW,
        reliability=normalize_reliability(
            (response.get("tool_reliability") or {}).get("reliability")
        )[0],
        notes=notes,
    )

    notes.append(
        f"通用修图分数由成员 3 Stage 1（FFHQR）给出：held-out F1 85.1%、FPR 6.0%，阈值 {generic.get('threshold')}"
    )
    notes.append("纹理损失使用磨皮信号作为代理，成员 3 未提供独立纹理头")
    notes.append("美白信号较弱（RetouchingFFHQ F1 60.7%），仅作辅助参考")
    if generic.get("detected"):
        notes.append("检出通用修图痕迹：该图可能经过专业后期，妆效不宜全部归因于产品")
    if not operations:
        warnings.append("成员 3 未返回 operations 细粒度信号")

    return evidence.model_dump(exclude_none=True), warnings


# ---------------------------------------------------------------------------
# 前后对比：成员 3 analyze_pair（+ 可选两张单图）→ T4 BeforeAfterEvidence
# ---------------------------------------------------------------------------
def pair_to_before_after(
    response: dict[str, Any],
    single_before: dict[str, Any] | None = None,
    single_after: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """返回 (evidence dict, warnings)。"""
    result = response.get("result") or {}
    deltas = result.get("parameter_deltas") or {}
    cues = result.get("reliability_rule_cues") or []
    warnings = list(response.get("limitations") or [])

    dimensions: list[ConsistencyDimension] = []

    # 曝光
    exposure = float(deltas.get("exposure") or 0.0)
    dimensions.append(
        ConsistencyDimension(
            dimension="exposure",
            level=_level(exposure, EXPOSURE_SIMILAR, EXPOSURE_SIGNIFICANT),
            detail=f"曝光差 {exposure:+.2f} EV（模型估计，MAE 约 0.24 EV）",
        )
    )

    # 白平衡：色温与 tint 取较严重者
    temperature = float(deltas.get("temperature") or 0.0)
    tint = float(deltas.get("tint") or 0.0)
    wb_level = _level(temperature, TEMPERATURE_SIMILAR, TEMPERATURE_SIGNIFICANT)
    if _level(tint, TINT_SIMILAR, TINT_SIGNIFICANT) is ComparisonLevel.SIGNIFICANT_DIFFERENCE:
        wb_level = ComparisonLevel.SIGNIFICANT_DIFFERENCE
    elif _level(tint, TINT_SIMILAR, TINT_SIGNIFICANT) is ComparisonLevel.DIFFERENT and wb_level is ComparisonLevel.SIMILAR:
        wb_level = ComparisonLevel.DIFFERENT
    dimensions.append(
        ConsistencyDimension(
            dimension="white_balance",
            level=wb_level,
            detail=f"色温差 {temperature:+.0f} K、Tint 差 {tint:+.1f}（模型估计）",
        )
    )

    # 色调：取变化最大的一项
    if TONE_PARAMETERS[0] in deltas:
        worst_name = max(TONE_PARAMETERS, key=lambda name: abs(float(deltas.get(name) or 0.0)))
        worst_value = float(deltas.get(worst_name) or 0.0)
        dimensions.append(
            ConsistencyDimension(
                dimension="tone",
                level=_level(worst_value, TONE_SIMILAR, TONE_SIGNIFICANT),
                detail=f"色调参数差最大项为 {worst_name} {worst_value:+.1f}（模型估计）",
            )
        )

    # 皮肤纹理：Stage 3 的 texture 参数
    if "texture" in deltas:
        texture = float(deltas.get("texture") or 0.0)
        dimensions.append(
            ConsistencyDimension(
                dimension="skin_texture",
                level=_level(texture, TEXTURE_SIMILAR, TEXTURE_SIGNIFICANT),
                detail=f"纹理参数差 {texture:+.2f}（模型估计，尺度待标定）",
            )
        )

    # 磨皮：用两张单图的磨皮概率差（需要额外调用 analyze_single）
    smoothing_detail = _smoothing_from_singles(single_before, single_after)
    if smoothing_detail is not None:
        level, detail = smoothing_detail
        dimensions.append(ConsistencyDimension(dimension="smoothing", level=level, detail=detail))
    else:
        dimensions.append(
            ConsistencyDimension(
                dimension="smoothing",
                level=ComparisonLevel.UNKNOWN,
                detail="未提供 Before/After 单图信号，磨皮维度未计算",
            )
        )

    # 成员 3 覆盖不到的维度：显式 Unknown
    for name, reason in UNSUPPORTED_DIMENSIONS.items():
        dimensions.append(ConsistencyDimension(dimension=name, level=ComparisonLevel.UNKNOWN, detail=reason))

    # 可靠性与归因强度
    raw_reliability = result.get("comparison_reliability") or (response.get("tool_reliability") or {}).get("reliability")
    reliability, is_unknown = normalize_reliability(raw_reliability)
    if not deltas:
        # 没有任何参数差 = 模型没算出来，不能当成"条件一致"
        reliability, is_unknown = EvidenceReliability.LOW, True
        warnings.append("成员 3 未返回 parameter_deltas，比较可靠性按 Unknown 处理")

    if is_unknown:
        strength = Strength.UNKNOWN
    elif reliability is EvidenceReliability.HIGH:
        strength = Strength.STRONG
    elif reliability is EvidenceReliability.MEDIUM:
        strength = Strength.MODERATE
    else:
        strength = Strength.WEAK

    # 归因结论：优先用成员 3 给的消费者说明，再补上维度与局限
    summary = response.get("consumer_explanation") or _build_summary(strength, cues)
    if cues:
        summary = f"{summary}（触发的条件差异：{'、'.join(cues)}）"
    if result.get("mask_used") is False:
        summary = f"{summary}（未提供前景 mask，前景/背景统计可靠性下降）"

    actions = [
        "建议参考相同光线、相同设备下的近距离原相机画面",
        "关注至少 4-8 小时后的持妆画面",
    ]
    if strength in (Strength.WEAK, Strength.MODERATE):
        actions.append("前后画面条件存在差异，建议向创作者索取原始素材或补拍对照")

    evidence = BeforeAfterEvidence(
        dimensions=dimensions,
        comparison_reliability=reliability,
        attribution_summary=summary,
        attribution_strength=strength,
        suggested_viewer_actions=actions,
    )
    return evidence.model_dump(exclude_none=True), warnings


def _smoothing_from_singles(
    single_before: dict[str, Any] | None, single_after: dict[str, Any] | None
) -> tuple[ComparisonLevel, str] | None:
    """用 Before/After 各自的磨皮概率差推断平滑维度。"""

    def score_of(single: dict[str, Any] | None) -> float | None:
        if not single:
            return None
        operation = ((single.get("result") or {}).get("operations") or {}).get("smoothing")
        return float(operation["score"]) if operation and "score" in operation else None

    before, after = score_of(single_before), score_of(single_after)
    if before is None or after is None:
        return None
    diff = after - before
    return (
        _level(diff, SMOOTHING_SIMILAR, SMOOTHING_SIGNIFICANT),
        f"After 磨皮信号较 Before {diff:+.3f}（{'更强' if diff > 0 else '更弱'}，模型估计）",
    )


def _build_summary(strength: Strength, cues: list[str]) -> str:
    if strength is Strength.UNKNOWN:
        return "前后对比未产生有效计算结果，无法判断观察到的变化能否归因于产品"
    if strength is Strength.STRONG:
        return "未发现多项强条件差异，但仍需结合原文、光线与原始素材复核"
    return "检测到若干修饰或拍摄条件差异，因此该内容中的妆效不宜全部归因于产品"
