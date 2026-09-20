"""成员 3（beauty_effect_attribution）集成包。

由 Main Agent 侧（A）维护，负责把成员 3 的独立 Tool 服务接入主链路：

    client.py   HTTP 客户端（超时 / 健康检查 / 解析 MediaRef）
    adapter.py  字段归一与语义映射（成员 3 契约 → 本项目 evidence schema）
    handlers.py ToolHandler 实现（real 优先，失败自动降级到原 mock）
    selftest.py 离线自检（不需要启动成员 3 服务）

设计原则见 docs/API_SPEC.md 与《成员 3 对接反馈 v1》。
"""
from __future__ import annotations

from ...config import settings
from .client import Member3Client, Member3Unavailable
from .handlers import Member3BeforeAfterHandler, Member3ForensicsHandler

__all__ = [
    "Member3Client",
    "Member3Unavailable",
    "Member3BeforeAfterHandler",
    "Member3ForensicsHandler",
    "register_member3_handlers",
]


def register_member3_handlers() -> list[str]:
    """把成员 3 的真实 handler 注册进 Tool 注册表（替换同名 mock）。

    仅当 settings.member3_enabled 为真时注册；注册后 handler 内部仍会在
    成员 3 服务不可用时自动回落到原 mock 实现。

    返回被替换的 tool 名称列表，便于启动日志与 /api/v1/tools 自检。
    """
    if not settings.member3_enabled:
        return []

    from ...tools import replace_handler

    client = Member3Client(
        base_url=settings.member3_base_url,
        timeout_seconds=settings.member3_timeout_seconds,
    )
    replace_handler(Member3ForensicsHandler(client))
    replace_handler(Member3BeforeAfterHandler(client))
    return ["image_forensics", "before_after"]
