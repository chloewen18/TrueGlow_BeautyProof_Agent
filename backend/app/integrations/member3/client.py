"""成员 3 Tool 服务的 HTTP 客户端。

成员 3 的服务独立部署（默认 http://127.0.0.1:8003），与 Main Agent 解耦：
  - torch 2.8 / torchvision 0.23 的模型依赖不进主工程环境
  - 超时、重试、降级、日志由 Main Agent 统一控制
  - 前端永不直连 8003，全部经 Main Agent 代理（因此成员 3 侧无需开 CORS）

服务不可用时统一抛出 Member3Unavailable，由 handlers.py 决定是否降级到 mock。
"""
from __future__ import annotations

import mimetypes
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

TOOL_NAME = "beauty_effect_attribution"
EXPECTED_SCHEMA_VERSION = "1.0.0"

# 契约 v1.0.0 中 Main Agent 可稳定依赖的字段；缺任意一个视为响应不可用。
REQUIRED_KEYS = ("schema_version", "tool", "status", "result", "evidence", "limitations")


class Member3Unavailable(RuntimeError):
    """成员 3 服务不可用：未启用 / 未启动 / 超时 / 响应结构非法。调用方应降级。"""


def _content_type(path: Path) -> str:
    return mimetypes.guess_type(str(path))[0] or "image/jpeg"


class Member3Client:
    """成员 3 beauty_effect_attribution 服务的客户端。"""

    def __init__(self, base_url: str = "", timeout_seconds: float = 30.0, enabled: bool = True):
        self.base_url = (base_url or "").rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.enabled = enabled

    # ---------------------------------------------------------------- 基础
    @property
    def available(self) -> bool:
        return self.enabled and bool(self.base_url)

    def _require(self) -> None:
        if not self.available:
            raise Member3Unavailable("成员 3 服务未启用（member3_enabled=false 或 base_url 为空）")

    def _post(self, path: str, files: dict, data: dict) -> dict[str, Any]:
        self._require()
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(f"{self.base_url}{path}", files=files, data=data)
                response.raise_for_status()
                payload = response.json()
        except Member3Unavailable:
            raise
        except Exception as exc:  # noqa: BLE001 - 统一转成降级信号
            raise Member3Unavailable(f"调用 {path} 失败: {exc}") from exc
        return self._validate(payload)

    @staticmethod
    def _validate(payload: dict[str, Any]) -> dict[str, Any]:
        """校验响应契约。

        成员 3 的 status 字段只有 ok/error 两态，且 error 时不一定带异常码，
        因此这里主动检查必填字段与 status，避免把半截响应当证据用。
        """
        if not isinstance(payload, dict):
            raise Member3Unavailable("响应不是 JSON 对象")
        missing = [key for key in REQUIRED_KEYS if key not in payload]
        if missing:
            raise Member3Unavailable(f"响应缺少必填字段: {missing}")
        if payload.get("status") != "ok":
            raise Member3Unavailable(f"成员 3 返回 status={payload.get('status')!r}")
        version = payload.get("schema_version")
        if version != EXPECTED_SCHEMA_VERSION:
            # 版本不一致不致命：记录后继续，由适配层按字段存在性兜底。
            payload.setdefault("limitations", []).append(
                f"schema_version {version} 与预期 {EXPECTED_SCHEMA_VERSION} 不一致，字段按存在性兜底解析"
            )
        return payload

    # ---------------------------------------------------------------- 接口
    def health(self) -> dict[str, Any]:
        if not self.available:
            return {"status": "disabled", "tool": TOOL_NAME}
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.get(f"{self.base_url}/health")
                response.raise_for_status()
                return response.json()
        except Exception as exc:  # noqa: BLE001
            raise Member3Unavailable(f"health 检查失败: {exc}") from exc

    def analyze_single(self, image_ref: str, request_id: str | None = None) -> dict[str, Any]:
        path = self.resolve(image_ref)
        with path.open("rb") as handle:
            files = {"image": (path.name, handle, _content_type(path))}
            return self._post(
                "/v1/analyze/single", files=files, data=self._request_id(request_id)
            )

    def analyze_pair(
        self,
        before_ref: str,
        after_ref: str,
        mask_ref: str | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        before_path = self.resolve(before_ref)
        after_path = self.resolve(after_ref)
        mask_path = self.resolve(mask_ref) if mask_ref else None

        files: dict[str, Any] = {}
        handles: list = []
        try:
            before_handle = before_path.open("rb")
            after_handle = after_path.open("rb")
            handles += [before_handle, after_handle]
            files["before"] = (before_path.name, before_handle, _content_type(before_path))
            files["after"] = (after_path.name, after_handle, _content_type(after_path))
            if mask_path:
                mask_handle = mask_path.open("rb")
                handles.append(mask_handle)
                files["mask"] = (mask_path.name, mask_handle, _content_type(mask_path))
            return self._post(
                "/v1/analyze/pair", files=files, data=self._request_id(request_id)
            )
        finally:
            for handle in handles:
                handle.close()

    # ---------------------------------------------------------------- 工具
    @staticmethod
    def _request_id(request_id: str | None) -> dict[str, str]:
        return {"request_id": request_id} if request_id else {}

    @staticmethod
    def resolve(ref: str) -> Path:
        """把 MediaRef.ref 解析为本地文件路径。

        - 本地文件路径：直接返回
        - http(s) URL：下载到临时文件后再上传（成员 3 服务只接受 multipart）
        - 其他（说明文字等）：抛 Member3Unavailable，由上层降级到 mock

        注意：临时文件不主动删除，交给操作系统清理，避免上传期间被回收。
        """
        parsed = urlparse(ref)
        if parsed.scheme in ("http", "https"):
            try:
                with httpx.Client(timeout=30.0) as client:
                    response = client.get(ref)
                    response.raise_for_status()
                    content = response.content
            except Exception as exc:  # noqa: BLE001
                raise Member3Unavailable(f"下载图片失败 {ref}: {exc}") from exc
            suffix = Path(parsed.path).suffix or ".jpg"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(content)
            return Path(tmp.name)

        path = Path(ref)
        if path.is_file():
            return path
        raise Member3Unavailable(f"无法解析为本地图片: {ref!r}")
