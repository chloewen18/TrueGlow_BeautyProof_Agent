"""Tool 基类与注册表。

每个 Tool 实现 ToolHandler：
  - handle(request) 返回统一 ToolResponse（含 evidence）
  - mock 模式由各 handler 内置；真实实现（成员 2/3/4 交付后）替换 register 的 handler 即可，
    对外 HTTP 契约不变。

注册表同时供 Main Agent 进程内调用（避免自建 HTTP 回路），
成员独立部署 Tool 服务时，Main Agent 可换用 HTTP 客户端（见 app/agent/tool_client.py）。
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

from ..schemas.common import ToolError, ToolRequest, ToolResponse, ToolMeta


class ToolHandler(ABC):
    """Tool 处理器抽象。"""

    name: str = ""
    description: str = ""
    version: str = "mock-1.0.0"
    mode: str = "mock"  # mock | real

    @abstractmethod
    def handle(self, request: ToolRequest) -> dict[str, Any]:
        """执行并返回 evidence dict（ToolResponse.evidence 的内容）。"""

    def run(self, request: ToolRequest) -> ToolResponse:
        t0 = time.perf_counter()
        try:
            evidence = self.handle(request)
            mode = "mock" if "signals" in request.payload else {"page_understanding": "real_rules", "source_trace": "real_exif", "text_integrity": "real_rules"}.get(self.name, "real")
            if evidence.get("file_info", {}).get("mode") == "real_exif":
                mode = "real_exif"
            evidence.setdefault("provenance", {}).update(mode=mode, engine=self.name, version=self.version)
            status = evidence.pop("_status", "success")
            error = None
        except Exception as exc:  # noqa: BLE001 - 统一转错误信封
            evidence = {}
            status = "error"
            error = ToolError(code="TOOL_INTERNAL_ERROR", message=str(exc))
            mode = "unavailable"
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return ToolResponse(
            tool=request.tool,
            request_id=request.request_id,
            status=status,
            evidence=evidence,
            meta=ToolMeta(version=self.version, model=mode, latency_ms=latency_ms),
            error=error,
        )


class ToolRegistry:
    """Tool 注册表：name -> handler。"""

    def __init__(self) -> None:
        self._handlers: dict[str, ToolHandler] = {}

    def register(self, handler: ToolHandler) -> None:
        if handler.name in self._handlers:
            raise ValueError(f"Tool 已注册: {handler.name}")
        self._handlers[handler.name] = handler

    def get(self, name: str) -> ToolHandler | None:
        return self._handlers.get(name)

    def list(self) -> list[dict[str, str]]:
        return [
            {"name": h.name, "description": h.description, "mode": h.mode, "version": h.version}
            for h in self._handlers.values()
        ]


registry = ToolRegistry()
