"""LLM Provider 工厂。"""
from __future__ import annotations

from .base import LLMProvider
from .deepseek import DeepSeekProvider
from .mock import MockProvider


def get_provider(name: str | None = None) -> LLMProvider:
    provider_name = (name or "").lower()
    if provider_name == "deepseek":
        return DeepSeekProvider()
    return MockProvider()
