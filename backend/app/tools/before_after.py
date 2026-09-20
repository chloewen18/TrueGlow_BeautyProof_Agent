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
    mode = "real_or_explicit_mock"
    version = "member3-1.1-integrated"

    def handle(self, request: ToolRequest) -> dict[str, Any]:
        p = request.payload
        if "signals" not in p:
            return self.real(request)
        s = p.get("signals", {})

        dims_raw = s.get("dimensions", p.get("dimensions"))
        # computed=False 表示没有拿到任何差异信号，即「未进行计算」。
        computed = bool(dims_raw)
        if dims_raw:
            dimensions = [ConsistencyDimension(**d) for d in dims_raw]
        else:
            # 修复：旧实现默认「全部 Similar + 归因 Strong」，等于一行没算就断言
            # "效果可归因于产品"，与项目「证据不足不判真」原则相反。未计算时一律 Unknown。
            dimensions = [
                ConsistencyDimension(dimension=name, level=ComparisonLevel.UNKNOWN, detail="未计算")
                for name in (
                    "face_angle",
                    "crop",
                    "exposure",
                    "white_balance",
                    "skin_texture",
                    "smoothing",
                )
            ]

        # 未计算时可靠性为 Low（没算就没有可靠证据），不得默认 High。
        default_reliability = "High" if computed else "Low"
        comp_reliability = EvidenceReliability(
            s.get("comparison_reliability", p.get("comparison_reliability", default_reliability))
        )

        # 归因强度：对比条件差异越大、可比较性越低 → 归因越不可靠
        significant = [d for d in dimensions if d.level in (ComparisonLevel.DIFFERENT, ComparisonLevel.SIGNIFICANT_DIFFERENCE)]
        if not computed:
            # 未计算：不得给出任何方向的归因结论
            attribution_strength = Strength.UNKNOWN
            summary = "未进行前后对比计算（当前为模拟实现），无法判断观察到的变化能否归因于产品"
        elif len(significant) == 0 or comp_reliability == EvidenceReliability.HIGH:
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

    def real(self, request):
        from ..integrations.visual import uploaded_path, pair, pair_difference
        p = request.payload
        if not p.get("before") or not p.get("after"):
            return {"dimensions": [], "comparison_reliability": "Unknown", "attribution_strength": "Unknown",
                    "attribution_summary": "缺少前后图片，未计算。", "_status": "partial"}
        before, after = uploaded_path(p["before"]), uploaded_path(p["after"])
        mask = uploaded_path(p["mask"]) if p.get("mask") else None
        result = pair(before, after, request.request_id, mask)
        difference = pair_difference(before, after)
        reliability = result["result"]["comparison_reliability"]
        if difference["status"] != "success":
            reliability = "Unknown"
        dims = [{"dimension": cue, "level": "Different", "detail": f"模型估计存在{cue}；不是产品因果证据"}
                for cue in result["result"]["reliability_rule_cues"]]
        if not dims:
            dims = [{"dimension": "条件差异", "level": "Unknown", "detail": "未触发强差异规则，不等于条件完全一致。"}]
        return {"dimensions": dims, "comparison_reliability": reliability,
                "attribution_summary": "仅评估对比条件；不能判断产品贡献。" if reliability != "Low" else result["consumer_explanation"],
                "attribution_strength": "Unknown", "member3_analysis": result, "difference": difference,
                "limitations": result["limitations"] + difference.get("limitations", []) +
                               ([difference["reason"]] if difference.get("reason") else []),
                "suggested_viewer_actions": ["补充同条件、无滤镜、可追溯的原始素材"]}


handler = BeforeAfterHandler()
