"""LLM Provider 抽象：Main Agent 的解释组织层。

原则（方案文档创新五）：检测模型负责发现证据、规则负责风险分级，
LLM 只在证据边界内组织解释——不替代检测、不输出证据之外的数字。
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """生成一段解释文本。失败时应抛出异常，由调用方降级到模板。"""

    def is_available(self) -> bool:
        return True
