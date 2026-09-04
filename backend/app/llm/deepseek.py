"""DeepSeek LLM Provider（OpenAI 兼容协议）。

通过 httpx 调用 /chat/completions。配置：
  LLM_PROVIDER=deepseek
  DEEPSEEK_API_KEY=sk-xxx
  DEEPSEEK_BASE_URL=https://api.deepseek.com/v1（默认）
  DEEPSEEK_MODEL=deepseek-chat（默认）
"""
from __future__ import annotations

import httpx

from ..config import settings
from .base import LLMProvider


class DeepSeekProvider(LLMProvider):
    name = "deepseek"

    def is_available(self) -> bool:
        return bool(settings.deepseek_api_key)

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        if not self.is_available():
            raise RuntimeError("DEEPSEEK_API_KEY 未配置")
        url = settings.deepseek_base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": settings.deepseek_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 1200,
        }
        headers = {"Authorization": f"Bearer {settings.deepseek_api_key}", "Content-Type": "application/json"}
        with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
