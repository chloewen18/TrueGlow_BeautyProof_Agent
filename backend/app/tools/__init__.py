"""Tool 包：注册全部内置 Tool（当前为 Mock 实现）。

成员 2/3/4 交付真实实现后，在此处用真实 handler 替换对应 mock 即可（保持同一契约）。
导入本包即自动注册（幂等），Main Agent 与 HTTP 端点共用同一注册表。
"""
from .base import ToolHandler, ToolRegistry, registry  # noqa: F401
from . import before_after, image_forensics, page_understanding, source_trace, text_integrity  # noqa: F401

_registered = False


def register_builtin_tools() -> ToolRegistry:
    """注册全部内置 Tool handler（幂等）。"""
    global _registered
    if _registered:
        return registry
    for module in (page_understanding, source_trace, image_forensics, before_after, text_integrity):
        registry.register(module.handler)
    _registered = True
    return registry


register_builtin_tools()


def replace_handler(handler: ToolHandler) -> None:
    """用真实实现替换 mock（同一 name 覆盖）。"""
    old = registry._handlers.pop(handler.name, None)  # noqa: SLF001
    registry.register(handler)
    if old:
        print(f"[tools] 已替换 {handler.name}: {old.mode} -> {handler.mode}")
