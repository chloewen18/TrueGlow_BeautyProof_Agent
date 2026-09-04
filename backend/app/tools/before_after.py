"""T4 前后对比一致性与妆效归因（Mock）。

真实实现（成员 3）：人脸关键点对齐 + 曝光/色温/清晰度/纹理条件差异计算。
Mock 版用 signals 注入各对比维度差异，输出归因结论与归因强度（Weak/Moderate/Strong）。
"""
from __future__ import annotations

from typing import Any

from ..schemas.common import ComparisonLevel, EvidenceReliability, Strength, ToolRequest
from ..schemas.tools import BeforeAfterEvidence, ConsistencyDimension
from .base import ToolHandler


class BeforeAfterHandler(ToolHandler):
    name = "before_after"
    description = "T4 前后对比一致性与妆效归因：人脸角度/裁切/曝光/白平衡/皮肤纹理/平滑强度 + 归因结论"
    mode = "mock"

    def handle(self, request: ToolRequest) -> dict[str, Any]:
        p = request.payload
        s = p.get("signals", {})

        dims_raw = s.get("dimensions", p.get("dimensions"))
        if dims_raw:
            dimensions = [ConsistencyDimension(**d) for d in dims_raw]
        else:
            # 默认中性：各维度 Similar，可比较
            dimensions = [
                ConsistencyDimension(dimension="face_angle", level=ComparisonLevel.SIMILAR, detail="角度一致"),
                ConsistencyDimension(dimension="crop", level=ComparisonLevel.SIMILAR, detail="裁切一致"),
                ConsistencyDimension(dimension="exposure", level=ComparisonLevel.SIMILAR, detail="曝光一致"),
                ConsistencyDimension(dimension="white_balance", level=ComparisonLevel.SIMILAR, detail="白平衡一致"),
                ConsistencyDimension(dimension="skin_texture", level=ComparisonLevel.SIMILAR, detail="纹理一致"),
                ConsistencyDimension(dimension="smoothing", level=ComparisonLevel.SIMILAR, detail="平滑强度一致"),
            ]

        comp_reliability = EvidenceReliability(s.get("comparison_reliability", p.get("comparison_reliability", "High")))

        # 归因强度：对比条件差异越大、可比较性越低 → 归因越不可靠
        significant = [d for d in dimensions if d.level in (ComparisonLevel.DIFFERENT, ComparisonLevel.SIGNIFICANT_DIFFERENCE)]
        if len(significant) == 0 or comp_reliability == EvidenceReliability.HIGH:
            attribution_strength = Strength.STRONG
            summary = "前后条件基本一致，观察到的变化可较合理地归因于产品"
        elif len(significant) <= 2:
            attribution_strength = Strength.MODERATE
            summary = "前后存在部分条件差异，效果归因需要谨慎"
        else:
            attribution_strength = Strength.WEAK
            summary = "前后画面条件差异显著，观察到的变化不能完全归因于产品"

        if s.get("attribution_summary"):
            summary = s["attribution_summary"]
        if s.get("attribution_strength"):
            attribution_strength = Strength(s["attribution_strength"])

        evidence = BeforeAfterEvidence(
            dimensions=dimensions,
            comparison_reliability=comp_reliability,
            attribution_summary=summary,
            attribution_strength=attribution_strength,
            suggested_viewer_actions=s.get(
                "suggested_viewer_actions",
                ["建议参考相同光线下的近距离原相机画面", "关注至少 4-8 小时后的持妆画面"],
            ),
        )
        return evidence.model_dump(exclude_none=True)


handler = BeforeAfterHandler()
