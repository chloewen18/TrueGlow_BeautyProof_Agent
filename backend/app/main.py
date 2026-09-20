"""TrueGlow 映真 - Main Agent 后端入口。

启动：
  cd backend
  uvicorn app.main:app --reload --port 8000
联调文档：docs/API_SPEC.md（OpenAPI 见 /docs）

公网部署前请设置 BEAUTYPROOF_API_KEY（见 backend/app/security.py 与 docs/DEPLOYMENT.md）。
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .agent.router import router as agent_router
from .media import router as media_router
from .tools import register_builtin_tools
from .tools.router import router as tools_router
from .deliverables import router as deliverables_router
from .member4_api import router as member4_router
from .volunteers import router as volunteer_router
from .config import settings
from .security import cleanup_runtime_files, install_security

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))


@asynccontextmanager
async def lifespan(_: FastAPI):
    cleanup_runtime_files()
    yield


app = FastAPI(
    title="TrueGlow 映真 - Main Agent",
    description="面向美妆内容生态的 AI 内容核验与信任辅助系统（一个 Main Agent + 五个专业 Tool + 结构化证据层）",
    version="1.0.0",
    lifespan=lifespan,
)

register_builtin_tools()

install_security(app)

app.include_router(tools_router)
app.include_router(agent_router)
app.include_router(media_router)
app.include_router(deliverables_router)
app.include_router(member4_router)
app.include_router(volunteer_router)


@app.get("/", summary="服务信息")
def root() -> dict:
    return {
        "service": "beautyproof-main-agent",
        "schema_version": "1.0.0",
        "docs": "/docs",
        "tools": "/api/v1/tools",
        "verify": "POST /api/v1/verify",
    }


@app.get("/healthz", summary="健康检查（公开）")
def healthz() -> dict:
    return {"status": "ok"}
