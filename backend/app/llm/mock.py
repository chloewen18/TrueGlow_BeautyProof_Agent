"""Mock LLM Provider：模板化解释生成，零依赖离线可用。

规则模板保证输出稳定、可测试；配置 LLM_PROVIDER=deepseek 后自动切换为真实 LLM。
"""
from __future__ import annotations

from .base import LLMProvider

_VERDICT_LABEL = {
    "verified": "已验证",
    "partially_suspicious": "部分可疑",
    "insufficient_evidence": "证据不足",
    "high_risk_misleading": "高风险误导",
}


class MockProvider(LLMProvider):
    name = "mock"

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        # 模板占位符替换：{verdict} 等由 reporter 预填充到 user_prompt 之外的 context
        # Mock 模式下 reporter 直接使用规则模板，无需真正解析 prompt。
        return ""

    @staticmethod
    def verdict_label(final_label: str) -> str:
        return _VERDICT_LABEL.get(final_label, final_label)
