"""T1 页面理解与任务拆解（Mock）。

真实实现（成员 1/前端联调后可迭代）：读取页面 HTML/截图 → 抽取标题正文图片视频关键帧 → OCR → 输出内容类型与任务清单。
Mock 版从 payload 直接读取内容信息，支持 signals 覆盖。
"""
from __future__ import annotations

from typing import Any

from ..schemas.common import ToolRequest
from ..schemas.tools import MediaRef, PageUnderstandingEvidence
from .base import ToolHandler


class PageUnderstandingHandler(ToolHandler):
    name = "page_understanding"
    description = "T1 页面理解与任务拆解：把用户浏览的内容转化为可分析对象与待核验任务清单"
    mode = "mock"

    def handle(self, request: ToolRequest) -> dict[str, Any]:
        p = request.payload
        signals = p.get("signals", {})

        evidence = PageUnderstandingEvidence(
            content_type=signals.get("content_type", p.get("content_type", "foundation_before_after_review")),
            product=signals.get("product", p.get("product")),
            claims=signals.get("claims", p.get("claims", [])),
            media_tasks=signals.get("media_tasks", p.get("media_tasks", [])),
            disclosure=signals.get("disclosure", p.get("disclosure", "unknown")),
            media=[MediaRef(**m) if isinstance(m, dict) else m for m in p.get("media", [])],
            notes=signals.get("notes", p.get("notes", [])),
        )
        # 默认任务拆解：根据内容类型给出建议核验任务
        if not evidence.media_tasks:
            if evidence.content_type in ("foundation_before_after_review", "before_after", "try_on_compilation"):
                evidence.media_tasks = ["before_after_consistency", "skin_smoothing", "texture_analysis"]
            elif "unboxing" in evidence.content_type or "single_try_on" in evidence.content_type:
                evidence.media_tasks = ["skin_smoothing", "texture_analysis"]
            else:
                evidence.media_tasks = ["source_trace", "text_integrity"]
        if not evidence.notes and evidence.claims:
            evidence.notes.append("已提取宣称，需核对是否存在长时段/同条件证据支持")
        return evidence.model_dump(exclude_none=True)


handler = PageUnderstandingHandler()
