"""任务规划：根据输入内容与用户上下文，决定调用哪些 Tool、传什么 payload。

原则（方案文档第五节）：Main Agent 不凭感觉判断，先拆解任务再调用 Tool。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolPlan:
    """单个 Tool 的调用计划。"""

    tool: str
    payload: dict[str, Any] = field(default_factory=dict)
    reason: str = ""


@dataclass
class VerifyPlan:
    """一次核验的完整调用计划。"""

    content_id: str
    steps: list[ToolPlan] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)  # 因输入缺失而跳过的 Tool 及原因


class Planner:
    def plan(self, payload: dict[str, Any]) -> VerifyPlan:
        content = payload.get("content", {})
        user_context = payload.get("user_context", {})
        cid = payload.get("content_id") or content.get("content_id") or "content_demo"
        signals = content.get("signals", {})  # 演示/联调用：按 tool 名注入模拟检测结果

        def with_signals(tool: str, base: dict[str, Any]) -> dict[str, Any]:
            s = signals.get(tool)
            if s:
                base["signals"] = s
            return base

        has_media = bool(content.get("media"))
        has_text = bool(content.get("body_text") or content.get("ocr_text") or content.get("text"))
        has_before_after = content.get("before_after") is not None or any(
            getattr(m, "kind", m.get("kind") if isinstance(m, dict) else "") == "before_after"
            for m in (content.get("media") or [])
        )
        has_images = any(
            (m.get("kind") if isinstance(m, dict) else getattr(m, "kind", "")) in ("image", "video_frame")
            for m in (content.get("media") or [])
        )

        steps: list[ToolPlan] = []
        skipped: list[str] = []

        # T1 页面理解：总是执行（从内容抽取产品/宣称/任务）
        steps.append(ToolPlan(tool="page_understanding", payload=with_signals("page_understanding", {**content, "user_context": user_context}), reason="把浏览内容转化为可分析对象与待核验任务"))

        # T2 来源溯源：有媒体文件才执行；无则跳过并标记（证据缺失不判假）
        if has_media or content.get("files"):
            steps.append(ToolPlan(tool="source_trace", payload=with_signals("source_trace", {"files": content.get("files") or content.get("media", []), "creator_submission": payload.get("creator_submission")}), reason="检查 EXIF/C2PA/元数据来源证据"))
        else:
            skipped.append("source_trace: 未提供媒体文件，来源维度证据缺失（不判伪造）")

        # T3 图像鉴伪：有图片/视频帧才执行
        if has_images:
            steps.append(ToolPlan(tool="image_forensics", payload=with_signals("image_forensics", {"images": [m for m in content.get("media", []) if (m.get("kind") if isinstance(m, dict) else getattr(m, "kind", "")) in ("image", "video_frame")]}), reason="检测拼接/替换/磨皮等视觉痕迹"))
        else:
            skipped.append("image_forensics: 未提供图片/视频帧")

        # T4 前后对比：有 before/after 对才执行
        ba = content.get("before_after")
        if ba:
            steps.append(ToolPlan(tool="before_after", payload=with_signals("before_after", {"before": ba["before"], "after": ba["after"], "claimed_effect": ba.get("claimed_effect")}), reason="判断前后对比可比较性与妆效归因"))
        else:
            skipped.append("before_after: 未提供 before/after 素材，妆效归因无法判断")

        # T5 文本完整性：有正文/OCR 才执行
        if has_text:
            steps.append(ToolPlan(tool="text_integrity", payload=with_signals("text_integrity", {"text": content.get("body_text") or content.get("text"), "ocr_text": content.get("ocr_text"), "comments": content.get("comments", []), "product": content.get("product"), "user_context": user_context}), reason="宣称提取、完整性检查、功效证据检索"))
        else:
            skipped.append("text_integrity: 未提供文本内容")

        return VerifyPlan(content_id=cid, steps=steps, skipped=skipped)


planner = Planner()
