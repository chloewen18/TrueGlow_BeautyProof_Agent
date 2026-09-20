"""T3 图像鉴伪与底妆修饰检测（Mock）。

真实实现（成员 2/3）：TruFor 等已有取证模型 inference（integrity score + manipulation map + reliability map）
+ 底妆专项分类器（磨皮/纹理损失/美白/瘦脸/曝光）。
Mock 版用 signals 直接注入检测结果；无 signals 时给出中性默认值。
"""
from __future__ import annotations

from typing import Any

from ..schemas.common import DetectStatus, EvidenceReliability, Severity, ToolRequest
from ..schemas.tools import ImageForensicsEvidence, ManipulationMapRef
from .base import ToolHandler


class ImageForensicsHandler(ToolHandler):
    name = "image_forensics"
    description = "T3 图像鉴伪与底妆修饰检测：拼接/局部替换/inpainting/AI生成 + 磨皮/纹理/美白/瘦脸/曝光"
    mode = "real_or_explicit_mock"
    version = "integrated-20260917"

    def handle(self, request: ToolRequest) -> dict[str, Any]:
        p = request.payload
        if "signals" not in p:
            return self.real(request)
        s = p.get("signals", {})

        evidence = ImageForensicsEvidence(
            integrity_score=float(s.get("integrity_score", p.get("integrity_score", 0.82))),
            manipulation_map=(
                ManipulationMapRef(**s["manipulation_map"]) if s.get("manipulation_map") else None
            ),
            reliability_map=(ManipulationMapRef(**s["reliability_map"]) if s.get("reliability_map") else None),
            local_replacement=DetectStatus(s.get("local_replacement", p.get("local_replacement", "Not detected"))),
            splicing=DetectStatus(s.get("splicing", p.get("splicing", "Not detected"))),
            inpainting=DetectStatus(s.get("inpainting", p.get("inpainting", "Not detected"))),
            ai_generated=DetectStatus(s.get("ai_generated", p.get("ai_generated", "Unknown"))),
            skin_smoothing=Severity(s.get("skin_smoothing", p.get("skin_smoothing", "Low"))),
            texture_loss=Severity(s.get("texture_loss", p.get("texture_loss", "Low"))),
            whitening=Severity(s.get("whitening", p.get("whitening", "Low"))),
            face_reshape=Severity(s.get("face_reshape", p.get("face_reshape", "Low"))),
            exposure_shift=Severity(s.get("exposure_shift", p.get("exposure_shift", "Low"))),
            reliability=EvidenceReliability(s.get("reliability", p.get("reliability", "Medium"))),
            notes=s.get("notes", p.get("notes", [])),
        )
        # 根据信号自动补充可解释说明
        if evidence.skin_smoothing == Severity.HIGH and not evidence.notes:
            evidence.notes.append("较强平滑处理，可能遮盖卡粉、起皮和真实毛孔堆积")
        if evidence.manipulation_map is None:
            evidence.manipulation_map = ManipulationMapRef(
                kind="description", value="（Mock）可疑区域热力图：待成员 2 接入 TruFor 后输出像素级 mask"
            )
        return evidence.model_dump(exclude_none=True)

    def real(self, request):
        from ..integrations.visual import uploaded_path, trufor, single
        images = request.payload.get("images") or []
        if not images or len(images) > 4:
            raise ValueError("Provide between one and four uploaded images")
        results, errors = [], []
        for media in images:
            path = uploaded_path(media)
            record = {"media_ref": media["ref"]}
            for name, call in [("trufor", lambda: trufor(path)), ("member3", lambda: single(path, request.request_id))]:
                try:
                    record[name] = call()
                except Exception as exc:
                    record[name] = {"status": "error", "mode": "unavailable", "error": str(exc)}
                    errors.append(f"{name}: {exc}")
            results.append(record)
        tf = [r["trufor"] for r in results if r["trufor"]["status"] == "success"]
        m3 = [r["member3"] for r in results if r["member3"]["status"] == "ok"]
        worst = max(tf, key=lambda r: r["trufor_score"]) if tf else {}
        def operation(name):
            return "Medium" if any(r["result"]["operations"][name]["detected"] for r in m3) else "Low" if m3 else "Unknown"
        return {"integrity_score": worst.get("integrity_score"),
                "trufor_score": worst.get("trufor_score"), "score_direction": worst.get("score_direction"),
                "manipulation_map": worst.get("manipulation_map"), "reliability_map": worst.get("reliability_map"),
                "local_replacement": "Unknown", "splicing": "Unknown", "inpainting": "Unknown", "ai_generated": "Unknown",
                "skin_smoothing": operation("smoothing"), "texture_loss": "Unknown", "whitening": operation("whitening"),
                "face_reshape": operation("facelifting"), "exposure_shift": "Unknown", "reliability": "Low",
                "per_image": results, "errors": errors, "_status": "partial" if errors else "success",
                "notes": ["成员三为真实模型推理，操作分数未完成跨域校准；不能证明修饰意图或产品因果。",
                          "强度0/30/60/90是训练域编辑档位，不是人体效果百分比。",
                          "汇总取本次图片最高可疑分数；每张图的原始输出分别保留。"] + errors}


handler = ImageForensicsHandler()
