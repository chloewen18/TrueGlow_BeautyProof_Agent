"""成员 3 真实实现的 ToolHandler（T3 图像取证 / T4 前后对比）。

两条铁律：

1. **real 优先，失败降级**：成员 3 服务没起、超时、响应结构非法，一律回落到原有
   mock handler，并把降级原因写进 `meta.warnings`——绝不能因为外部服务挂了就报错，
   也绝不能悄悄用 mock 数据冒充真实推理。
2. **不输出意图**：成员 3 只给证据信号，本层不做"造假"判定，也不生成产品贡献百分比。

`mode` 在每次调用时重写，因此 `ToolResponse.meta.model` 与 `/api/v1/tools`
反映的是**本次**实际执行模式，便于前端显示真实/模拟徽章。
"""
from __future__ import annotations

from typing import Any

from ...schemas.common import ToolRequest, ToolResponse
from ...tools.base import ToolHandler
from ...tools.before_after import handler as mock_before_after
from ...tools.image_forensics import handler as mock_image_forensics
from .adapter import pair_to_before_after, single_to_image_forensics
from .client import Member3Client, Member3Unavailable

REAL_VERSION = "member3-1.1.0"


def _surface_provenance(handler: "_Member3HandlerMixin", response: dict[str, Any]) -> None:
    """把成员 3 v1.1 的 engine/provenance 溯源信息接到本次调用的 warnings，
    供前端「技术详情」展开显示真实/模拟徽章背后的依据。

    仅当权重完整性不是 verified 时才升级为强提醒；verified 时只做一条普通记录。
    """
    eng = response.get("engine") or {}
    prov = response.get("provenance") or {}
    integrity = prov.get("model_integrity", "unknown")
    line = f"成员3 溯源：引擎 v{eng.get('version', '?')} · 权重完整性 {integrity} · 设备 {eng.get('device', '?')}"
    if integrity != "verified":
        handler._pending_warnings.append(f"[权重异常] {line}")
    else:
        handler._pending_warnings.append(line)


class _Member3HandlerMixin:
    """real/mock 双路与 warnings 收集的公共逻辑。"""

    client: Member3Client
    _fallback: ToolHandler

    def run(self, request: ToolRequest) -> ToolResponse:
        # 单次调用内收集警告（demo 为串行执行；并发场景应改为 contextvar）
        self._pending_warnings: list[str] = []
        response = super().run(request)  # type: ignore[misc] - 混入 ToolHandler
        if self._pending_warnings:
            merged = list(response.meta.warnings) + self._pending_warnings
            response.meta.warnings = list(dict.fromkeys(merged))
        return response

    def _degrade(self, reason: str, request: ToolRequest, engine: str) -> dict[str, Any]:
        self.mode = f"mock(fallback: {reason})"
        self._pending_warnings.append(
            f"成员 3 服务不可用（{reason}），已降级到 mock 实现，本次结论不作为真实证据"
        )
        self._pending_warnings.append(f"预期引擎: {engine}")
        return self._fallback.handle(request)


class Member3ForensicsHandler(_Member3HandlerMixin, ToolHandler):
    """T3 图像鉴伪与底妆修饰：成员 3 Stage 1（通用修图）+ Stage 2（四类美颜）。"""

    name = "image_forensics"
    description = "T3 图像鉴伪与底妆修饰检测：成员 3 通用修图二分类 + 磨皮/美白/瘦脸/大眼辅助信号"
    mode = "real"
    version = REAL_VERSION

    def __init__(self, client: Member3Client) -> None:
        self.client = client
        self._fallback = mock_image_forensics

    def handle(self, request: ToolRequest) -> dict[str, Any]:
        self.mode = "real"
        payload = request.payload
        images = payload.get("images") or []
        task = payload.get("task", "both")

        if not images:
            return self._degrade("payload 未提供 images", request, "stage1_ffhqr+stage2_rffhq")
        # 成员 3 只覆盖修饰检测，纯鉴伪（拼接/AI 生成）仍走 mock
        if task == "forensics":
            return self._degrade("task=forensics 超出成员 3 能力范围", request, "stage1_ffhqr+stage2_rffhq")

        try:
            response = self.client.analyze_single(
                images[0].get("ref") if isinstance(images[0], dict) else str(images[0]),
                request_id=request.request_id,
            )
        except Member3Unavailable as exc:
            return self._degrade(str(exc), request, "stage1_ffhqr+stage2_rffhq")

        evidence, warnings = single_to_image_forensics(response)
        self._pending_warnings.extend(warnings)
        _surface_provenance(self, response)
        return evidence


class Member3BeforeAfterHandler(_Member3HandlerMixin, ToolHandler):
    """T4 前后对比一致性与妆效归因：成员 3 Stage 3（条件参数差）+ 可选 Stage 2 磨皮对比。"""

    name = "before_after"
    description = "T4 前后对比一致性与妆效归因：曝光/白平衡/色调参数差 + 磨皮信号对比 + 归因可靠性"
    mode = "real"
    version = REAL_VERSION

    def __init__(self, client: Member3Client) -> None:
        self.client = client
        self._fallback = mock_before_after

    def handle(self, request: ToolRequest) -> dict[str, Any]:
        self.mode = "real"
        payload = request.payload
        engine = "stage3_ppr10k(+stage2_rffhq)"

        before = payload.get("before") or {}
        after = payload.get("after") or {}
        before_ref = before.get("ref") if isinstance(before, dict) else None
        after_ref = after.get("ref") if isinstance(after, dict) else None
        if not before_ref or not after_ref:
            return self._degrade("payload 未提供完整的 before/after", request, engine)

        mask_ref = payload.get("mask_ref")
        compare_smoothing = request.options.get("compare_smoothing", True)

        try:
            pair_response = self.client.analyze_pair(
                before_ref, after_ref, mask_ref=mask_ref, request_id=request.request_id
            )
            single_before = single_after = None
            if compare_smoothing:
                # 磨皮维度成员 3 的 pair 接口不直接给，补两次单图调用取概率差
                try:
                    single_before = self.client.analyze_single(before_ref, request_id=request.request_id)
                    single_after = self.client.analyze_single(after_ref, request_id=request.request_id)
                except Member3Unavailable:
                    self._pending_warnings.append("单图调用失败，磨皮维度按未计算处理")
                    single_before = single_after = None
        except Member3Unavailable as exc:
            return self._degrade(str(exc), request, engine)

        evidence, warnings = pair_to_before_after(pair_response, single_before, single_after)
        self._pending_warnings.extend(warnings)
        _surface_provenance(self, pair_response)
        return evidence
