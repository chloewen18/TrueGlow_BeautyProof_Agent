"""T2 来源溯源与创作者证明（Mock）。

真实实现（成员 2）：解析 EXIF/XMP/C2PA、文件哈希；调用 C2PA 验证工具链。
Mock 版根据 signals 返回 c2pa 状态；遵循方案文档原则：
  - C2PA 存在且验证通过 → 高权重来源证据
  - C2PA 不存在 → Unknown，不直接判伪造
  - 元数据缺失 → 提示平台压缩可能，继续视觉取证
"""
from __future__ import annotations

from typing import Any

from ..schemas.common import ToolRequest
from ..schemas.tools import C2paInfo, SourceTraceEvidence
from .base import ToolHandler


class SourceTraceHandler(ToolHandler):
    name = "source_trace"
    description = "T2 来源溯源与创作者证明：EXIF/XMP、C2PA、创建工具、元数据异常、文件哈希"
    mode = "mock"

    def handle(self, request: ToolRequest) -> dict[str, Any]:
        p = request.payload
        signals = p.get("signals", {})

        c2pa_status = signals.get("c2pa_status", p.get("c2pa_status", "absent"))
        c2pa = C2paInfo(status=c2pa_status, detail=signals.get("c2pa_detail"))

        metadata_complete = signals.get("metadata_complete", p.get("metadata_complete", False))
        anomalies = signals.get("metadata_anomalies", p.get("metadata_anomalies", []))

        # 结论文本遵循方案文档原则
        if c2pa_status == "valid":
            conclusion = "C2PA 存在且验证通过，可作为高权重来源证据"
        elif c2pa_status == "invalid":
            conclusion = "C2PA 签名验证失败，来源证据不可信"
        else:
            conclusion = "C2PA 不存在，来源状态 Unknown；不做二元判假，继续调用视觉取证"
            if not metadata_complete:
                conclusion += "；元数据可能受平台压缩/转码影响"

        evidence = SourceTraceEvidence(
            c2pa=c2pa,
            exif=signals.get("exif", p.get("exif", {})),
            metadata_complete=metadata_complete,
            metadata_anomalies=anomalies,
            ai_declared=signals.get("ai_declared", p.get("ai_declared")),
            file_info=signals.get("file_info", p.get("file_info", {})),
            creator_submission_status=signals.get("creator_submission_status", "none"),
            conclusion=conclusion,
        )
        return evidence.model_dump(exclude_none=True)


handler = SourceTraceHandler()
