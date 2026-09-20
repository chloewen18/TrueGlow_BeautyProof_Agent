"""公网部署安全层：API Key 校验、基础限流、CORS 收敛、运行时文件清理。

设计原则：全部通过环境变量开关，**默认关闭**，因此不影响本地开发与演示；
一旦设置了对应环境变量即在公网生效。

相关环境变量（见 .env.example）：
  BEAUTYPROOF_API_KEY             设置后 /api/* 必须携带 X-API-Key
  BEAUTYPROOF_CORS_ORIGINS        逗号分隔的允许来源；留空 = 仅同源
  BEAUTYPROOF_RATE_LIMIT_PER_MINUTE  单 IP 每分钟请求上限；0 = 关闭
  BEAUTYPROOF_RUNTIME_RETENTION_HOURS  上传/产物文件保留时长；0 = 不清理
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Deque

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings

logger = logging.getLogger(__name__)

# 这些路径必须保持公开：浏览器 <img>/<video> 标签无法携带自定义请求头，
# 且文件名本身为随机 UUID，不可枚举。
PUBLIC_PREFIXES = ("/api/v1/uploads/", "/api/v1/artifacts/")
PUBLIC_EXACT = ("/", "/healthz", "/docs", "/redoc", "/openapi.json")


def _is_public(path: str) -> bool:
    return path in PUBLIC_EXACT or path.startswith(PUBLIC_PREFIXES)


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """设置了 BEAUTYPROOF_API_KEY 时，对 /api/* 校验 X-API-Key。"""

    async def dispatch(self, request: Request, call_next):
        if not settings.api_key:
            return await call_next(request)

        path = request.url.path
        if _is_public(path) or not path.startswith("/api/"):
            return await call_next(request)

        provided = request.headers.get("x-api-key") or request.query_params.get("api_key", "")
        if provided != settings.api_key:
            return JSONResponse(
                {
                    "status": "error",
                    "error": {"code": "unauthorized", "message": "缺少或错误的 API Key"},
                },
                status_code=401,
            )
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """进程内滑动窗口限流（单 IP）。多实例部署需换成 Redis 等共享存储。"""

    def __init__(self, app):
        super().__init__(app)
        self._hits: dict[str, Deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        limit = settings.rate_limit_per_minute
        if limit <= 0 or _is_public(request.url.path):
            return await call_next(request)

        ip = request.client.host if request.client else "unknown"
        now = time.time()
        bucket = self._hits[ip]
        while bucket and now - bucket[0] > 60:
            bucket.popleft()

        if len(bucket) >= limit:
            return JSONResponse(
                {
                    "status": "error",
                    "error": {"code": "rate_limited", "message": "请求过于频繁，请稍后重试"},
                },
                status_code=429,
                headers={"Retry-After": "60"},
            )

        bucket.append(now)
        if len(self._hits) > 5000:  # 防止字典无限膨胀
            self._hits.clear()
        return await call_next(request)


def install_security(app: FastAPI) -> None:
    """按配置装配安全中间件。

    add_middleware 是 LIFO：最后添加的最先执行（最外层）。
    期望的执行顺序（外→内）：CORS → 限流 → 鉴权 → 业务。
    这样限流能挡住携带错误 API Key 的暴力尝试，CORS 头也能附加到错误响应上。
    """
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]

    app.add_middleware(ApiKeyMiddleware)
    app.add_middleware(RateLimitMiddleware)
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "X-API-Key"],
        )
    logger.info(
        "security: api_key=%s rate_limit=%s/min cors_origins=%s",
        "on" if settings.api_key else "off",
        settings.rate_limit_per_minute,
        origins or "same-origin",
    )


def cleanup_runtime_files() -> int:
    """删除超过保留期的上传文件与检测产物，返回删除数量。"""
    hours = settings.runtime_retention_hours
    if hours <= 0:
        return 0

    cutoff = time.time() - hours * 3600
    removed = 0
    for sub in ("uploads", "artifacts"):
        root = settings.resolved_data_dir / sub
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.is_file():
                try:
                    if path.stat().st_mtime < cutoff:
                        path.unlink()
                        removed += 1
                except OSError:
                    continue
    if removed:
        logger.info("runtime cleanup: removed %d expired files", removed)
    return removed
