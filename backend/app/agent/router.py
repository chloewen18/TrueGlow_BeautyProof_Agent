"""Main Agent 编排 API：/verify 闭环 + 分步端点 + 补证复核 + 日志查询 + 素材上传。

统一响应信封（已冻结，见 docs/API_SPEC.md §6.1）：
  { "request_id", "status", "result": {...}, "meta": {...}, "error": null }
"""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from ..config import settings
from ..logging.trace import trace
from ..media import parse_multipart_verify
from ..schemas.common import ApiResponse, ToolError, ToolMeta
from ..storage.evidence_store import evidence_store
from .orchestrator import main_agent
from .planner import planner

router = APIRouter(prefix="/api/v1", tags=["agent"])


def _mock_warnings() -> list[str]:
    """Mock 模式下给出明确提示，便于前端联调时区分模拟/真实数据。"""
    if settings.llm_provider == "mock":
        return ["解释层使用规则模板；各检测模块真实/模拟状态请查看tool_calls及provenance"]
    return []


def _meta(latency_ms: int, warnings: list[str] | None = None) -> ToolMeta:
    return ToolMeta(version="1.0.0", model=settings.llm_provider, latency_ms=latency_ms, warnings=warnings or [])


@router.get("/health", summary="健康检查")
def health() -> dict:
    return {"status": "ok", "service": "beautyproof-main-agent", "schema_version": "1.0.0"}


@router.post("/verify", response_model=ApiResponse, summary="一键完整核验（识别→判断→决策闭环）")
async def verify(request: Request) -> ApiResponse:
    """支持两种 content-type：
    - application/json：body 即 payload（见 API_SPEC §6.1）
    - multipart/form-data：表单字段 payload(JSON) + files(图片/视频)，后端自动保存并注入 content.media
    """
    t0 = time.perf_counter()
    ctype = request.headers.get("content-type", "")
    try:
        if ctype.startswith("multipart/form-data"):
            payload, _uploaded = await parse_multipart_verify(request)
        else:
            payload = await request.json()
        result = await run_in_threadpool(main_agent.verify, payload)
        return ApiResponse(
            request_id=result["request_id"],
            status="success",
            result=result,
            meta=_meta(int((time.perf_counter() - t0) * 1000), _mock_warnings()),
        )
    except Exception as exc:  # noqa: BLE001
        return ApiResponse(
            request_id="",
            status="error",
            result={},
            meta=_meta(int((time.perf_counter() - t0) * 1000)),
            error=ToolError(code="VERIFY_FAILED", message=str(exc)),
        )


@router.post("/agents/plan", response_model=ApiResponse, summary="步骤1：任务拆解（返回调用计划，不执行）")
def plan_only(payload: dict[str, Any]) -> ApiResponse:
    plan = planner.plan(payload)
    return ApiResponse(
        request_id="plan_preview",
        status="success",
        result={
            "content_id": plan.content_id,
            "steps": [{"tool": s.tool, "reason": s.reason, "payload": s.payload} for s in plan.steps],
            "skipped": plan.skipped,
        },
    )


@router.post("/creators/review", response_model=ApiResponse, summary="创作者补证复核（重新判断并更新结论）")
def review(payload: dict[str, Any]) -> ApiResponse:
    """payload: {content_id, creator_submission:{...}, original_request_id, recheck?:{tool:payload}}

    返回结构（已冻结，见 API_SPEC §6.2）含 before/after 结论对比、复核说明、可信妆效凭证。
    """
    t0 = time.perf_counter()
    content_id = payload.get("content_id")
    submission = payload.get("creator_submission", {})
    original_rid = payload.get("original_request_id")
    recheck = payload.get("recheck")
    if not content_id:
        return ApiResponse(
            request_id="", status="error", result={},
            meta=_meta(int((time.perf_counter() - t0) * 1000)),
            error=ToolError(code="MISSING_CONTENT_ID", message="缺少 content_id"),
        )
    original = None
    if original_rid:
        original = evidence_store.load_evidence(original_rid)
    if original is None:
        return ApiResponse(
            request_id="", status="error", result={},
            meta=_meta(int((time.perf_counter() - t0) * 1000)),
            error=ToolError(code="ORIGINAL_NOT_FOUND", message="未找到原始核验记录，请提供 original_request_id"),
        )
    try:
        result = main_agent.review(
            content_id, submission, original, recheck=recheck, original_request_id=original_rid,
        )
        return ApiResponse(
            request_id=result["request_id"],
            status="success",
            result=result,
            meta=_meta(int((time.perf_counter() - t0) * 1000), _mock_warnings()),
        )
    except Exception as exc:  # noqa: BLE001
        return ApiResponse(
            request_id="", status="error", result={},
            meta=_meta(int((time.perf_counter() - t0) * 1000)),
            error=ToolError(code="REVIEW_FAILED", message=str(exc)),
        )


@router.get("/logs/{request_id}", summary="查询某次请求的全链路追踪日志")
def get_logs(request_id: str) -> dict:
    logs = trace.read(request_id)
    if not logs:
        raise HTTPException(status_code=404, detail=f"未找到 request_id={request_id} 的日志")
    return {"request_id": request_id, "entries": logs}


@router.get("/evidence/{request_id}", summary="查询某次请求落盘的结构化证据")
def get_evidence(request_id: str) -> dict:
    data = evidence_store.load_evidence(request_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"未找到 request_id={request_id} 的证据")
    return {"request_id": request_id, "evidence": data}
