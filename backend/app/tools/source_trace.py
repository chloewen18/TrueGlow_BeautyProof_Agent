"""T2 来源溯源与创作者证明（Mock）。

真实实现（成员 2）：解析 EXIF/XMP/C2PA、文件哈希；调用 C2PA 验证工具链。
Mock 版根据 signals 返回 c2pa 状态；遵循方案文档原则：
  - C2PA 存在且验证通过 → 高权重来源证据
  - C2PA 不存在 → Unknown，不直接判伪造
  - 元数据缺失 → 提示平台压缩可能，继续视觉取证
"""
from __future__ import annotations

from typing import Any
import hashlib
from pathlib import Path

from ..config import settings
from ..integrations.metadata_parser import extract_metadata

from ..schemas.common import ToolRequest
from ..schemas.tools import C2paInfo, SourceTraceEvidence
from .base import ToolHandler


# ---------------------------------------------------------------------------
# C2PA 预检：不依赖第三方库，只做「有没有 C2PA 数据」的存在性判断。
# 签名验证仍需 c2pa-python（成员 2 后续接入），本函数不冒充验证结果。
# ---------------------------------------------------------------------------
_C2PA_MAGIC = b"c2pa"
_C2PA_SCAN_BYTES = 8 * 1024 * 1024  # 只扫前 8MB，避免大文件全量读取


def inspect_c2pa(path: Path) -> C2paInfo:
    """判断文件中是否存在 C2PA / Content Credentials 数据。

    返回状态：
      - absent            未检测到 C2PA 数据（不含凭证，或已被平台剥离）→ Unknown，不等于伪造
      - not_verified      检测到 C2PA 数据，但当前环境无签名验证库
      - unsupported_format 文件格式不在可检查范围内
      - error             读取失败

    注意：本函数只判断「存在性」，不验证签名。
    """
    try:
        suffix = path.suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".avif", ".heic", ".heif"}:
            return C2paInfo(
                status="unsupported_format",
                detail=f"当前预检不支持该文件格式（{suffix or '未知'}），无法判断是否存在 C2PA 数据",
            )

        with path.open("rb") as fh:
            head = fh.read(_C2PA_SCAN_BYTES)

        # C2PA 以 JUMBF 盒嵌入，标签与断言中会出现 "c2pa" 字符串；
        # PNG 另有 caBX 块。两者任一命中即认为"可能存在 C2PA 数据"。
        has_jumbf = _C2PA_MAGIC in head
        has_cabx = b"caBX" in head

        if not (has_jumbf or has_cabx):
            return C2paInfo(
                status="absent",
                detail="未检测到 C2PA 数据：文件可能不含 Content Credentials，或已在上平台时被剥离。这不代表伪造。",
            )

        where = "PNG caBX 块" if has_cabx else "JUMBF 盒"
        return C2paInfo(
            status="not_verified",
            detail=(
                f"检测到疑似 C2PA 数据（{where}），但当前环境未安装签名验证库（c2pa-python），"
                "无法确认签名是否有效。此状态为 Unknown，不作为判真或判假依据。"
            ),
        )
    except Exception as exc:  # pragma: no cover
        return C2paInfo(status="error", detail=f"C2PA 预检失败：{exc}")


def _merge_c2pa(paths: list[Path]) -> C2paInfo:
    """多文件时的合并策略：只要有一个文件不含 C2PA，整体就不能说"有凭证"。"""
    infos = [inspect_c2pa(p) for p in paths]
    if not infos:
        return C2paInfo(status="error", detail="无可检查的文件")
    if any(i.status == "not_verified" for i in infos) and all(
        i.status == "not_verified" for i in infos
    ):
        return C2paInfo(
            status="not_verified",
            detail=f"全部 {len(infos)} 个文件均检测到疑似 C2PA 数据，但无签名验证库，状态 Unknown。",
        )
    if all(i.status == "absent" for i in infos):
        return C2paInfo(
            status="absent",
            detail=f"全部 {len(infos)} 个文件均未检测到 C2PA 数据。这不代表伪造。",
        )
    return C2paInfo(
        status="not_verified",
        detail=(
            f"{len(infos)} 个文件中 C2PA 状态不一致（部分存在、部分缺失），"
            "且无签名验证库。整体按 Unknown 处理。"
        ),
    )


class SourceTraceHandler(ToolHandler):
    name = "source_trace"
    description = "T2 来源溯源与创作者证明：EXIF/XMP、C2PA、创建工具、元数据异常、文件哈希"
    mode = "hybrid"
    version = "exif-1.0.0"

    def handle(self, request: ToolRequest) -> dict[str, Any]:
        p = request.payload
        files = p.get("files", [])
        if any(str(item.get("ref", "")).startswith("uploads/") for item in files):
            records = []
            targets: list[Path] = []
            root = (settings.resolved_data_dir / "uploads").resolve()
            for item in files:
                ref = str(item.get("ref", ""))
                target = (settings.resolved_data_dir / ref).resolve()
                if root not in target.parents or not target.is_file():
                    raise ValueError("Invalid uploaded media reference")
                metadata = extract_metadata(str(target))
                records.append({
                    "ref": ref, "exif": metadata["exif"],
                    "has_metadata": metadata["has_metadata"],
                    "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                    "size_bytes": target.stat().st_size,
                })
                targets.append(target)

            c2pa_info = inspect_c2pa(targets[0]) if len(targets) == 1 else _merge_c2pa(targets)
            return SourceTraceEvidence(
                c2pa=c2pa_info,
                exif={r["ref"]: r["exif"] for r in records},
                metadata_complete=False,
                file_info={
                    "files": records,
                    "mode": "real_exif",
                    "metadata_completeness": "not_assessed",
                    "c2pa_check": "presence_only",  # 仅做存在性预检，未做签名验证
                },
                creator_submission_status="received" if p.get("creator_submission") else "none",
                conclusion=(
                    "已读取上传文件的 EXIF 和 SHA256；EXIF 存在不代表来源真实，缺失也不代表伪造。"
                    f"C2PA：{c2pa_info.detail or c2pa_info.status}"
                ),
            ).model_dump(exclude_none=True)
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
