"""Tool HTTP 端点：POST /api/v1/tools/{name}。

统一信封契约见 docs/API_SPEC.md。各成员可用 curl 直接联调自己的 Tool：
  curl -X POST http://127.0.0.1:8000/api/v1/tools/source_trace \
    -H 'Content-Type: application/json' \
    -d '{"tool":"source_trace","request_id":"demo-1","payload":{...}}'
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..schemas.common import ToolError, ToolRequest, ToolResponse
from .base import registry

router = APIRouter(prefix="/api/v1/tools", tags=["tools"])


@router.get("", summary="列出全部 Tool")
def list_tools() -> dict:
    return {"tools": registry.list()}


@router.get("/{name}", summary="查询单个 Tool 信息")
def get_tool(name: str) -> dict:
    handler = registry.get(name)
    if not handler:
        raise HTTPException(status_code=404, detail=f"Tool 不存在: {name}")
    return {"name": handler.name, "description": handler.description, "mode": handler.mode, "version": handler.version}


@router.post("/{name}", response_model=ToolResponse, summary="调用 Tool")
def call_tool(name: str, req: ToolRequest) -> ToolResponse:
    handler = registry.get(name)
    if not handler:
        return ToolResponse(
            tool=name,
            request_id=req.request_id,
            status="error",
            evidence={},
            error=ToolError(code="TOOL_NOT_FOUND", message=f"Tool 不存在: {name}"),
        )
    # 强制 tool 字段与路径一致，避免误调用
    req.tool = name
    resp = handler.run(req)
    if resp.status == "error" and resp.error is not None:
        # 5xx 语义化返回，方便联调排查
        raise HTTPException(status_code=500, detail=resp.error.model_dump())
    return resp
