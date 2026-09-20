"""TrueGlow 映真 - Main Agent 后端入口。

启动：
  cd backend
  uvicorn app.main:app --reload --port 8000
联调文档：docs/API_SPEC.md（OpenAPI 见 /docs）
"""
from __future__ import annotations

from fastapi import FastAPI

from .agent.router import router as agent_router
from .config import settings
from .integrations.member3 import register_member3_handlers
from .media import router as media_router
from .tools import register_builtin_tools
from .tools.router import router as tools_router
from .deliverables import router as deliverables_router
from .member4_api import router as member4_router

app = FastAPI(
    title="TrueGlow 映真 - Main Agent",
    description="面向美妆内容生态的 AI 内容核验与信任辅助系统（一个 Main Agent + 五个专业 Tool + 结构化证据层）",
    version="1.0.0",
)

register_builtin_tools()
# 成员 3 真实模型服务（member3_enabled=true 时替换 image_forensics / before_after）
MEMBER3_TOOLS = register_member3_handlers()

app.include_router(tools_router)
app.include_router(agent_router)
app.include_router(media_router)
app.include_router(deliverables_router)
app.include_router(member4_router)


@app.get("/", summary="服务信息")
def root() -> dict:
    return {
        "service": "beautyproof-main-agent",
        "schema_version": "1.0.0",
        "docs": "/docs",
        "tools": "/api/v1/tools",
        "verify": "POST /api/v1/verify",
        "member3_tools": MEMBER3_TOOLS,
    }
