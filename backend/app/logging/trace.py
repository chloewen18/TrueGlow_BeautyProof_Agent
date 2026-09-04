"""日志追踪：JSONL 全链路追踪，每个请求一个文件。

记录：请求开始/结束、每次 Tool 调用（名称/状态/耗时）、证据融合摘要、分级结论。
用于：过程可追溯（方案文档：记录每次 Tool 调用和结论来源，保证流程可追溯）。
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import settings

_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class TraceLogger:
    """按 request_id 写 JSONL 追踪日志。"""

    def __init__(self, logs_dir: Path | None = None) -> None:
        self.logs_dir = logs_dir or settings.logs_dir
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, request_id: str) -> Path:
        # 避免路径注入
        safe = request_id.replace("/", "_").replace("\\", "_")
        return self.logs_dir / f"{safe}.jsonl"

    def log(self, request_id: str, event: str, **fields: Any) -> None:
        record = {"ts": _now(), "request_id": request_id, "event": event, **fields}
        with _lock:
            with self._path(request_id).open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def read(self, request_id: str) -> list[dict[str, Any]]:
        path = self._path(request_id)
        if not path.exists():
            return []
        with path.open(encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]


trace = TraceLogger()
