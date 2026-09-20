"""成员 3 适配层离线自检（不需要启动成员 3 服务）。

用法：
    cd backend
    python -m app.integrations.member3.selftest

覆盖：方向转换、大小写归一、Unknown 兜底、分级阈值、降级分支。
"""
from __future__ import annotations

from .adapter import normalize_reliability, pair_to_before_after, single_to_image_forensics

FAILURES: list[str] = []


def check(name: str, actual, expected) -> None:
    ok = actual == expected
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {actual!r}" + ("" if ok else f" != {expected!r}"))
    if not ok:
        FAILURES.append(name)


def fake_single(generic_score: float, operations: dict | None = None) -> dict:
    return {
        "schema_version": "1.0.0",
        "tool": "beauty_effect_attribution",
        "request_id": "selftest",
        "status": "ok",
        "result": {
            "generic_retouch": {"score": generic_score, "threshold": 0.731, "detected": generic_score >= 0.731,
                                "risk_level": "high", "model_route": "stage1_ffhqr"},
            "operations": operations or {},
        },
        "evidence": [],
        "limitations": ["Stage 2 未在社交媒体域校准"],
    }


def fake_pair(deltas: dict, cues: list, reliability: str = "high", mask_used: bool = True) -> dict:
    return {
        "schema_version": "1.0.0",
        "tool": "beauty_effect_attribution",
        "request_id": "selftest",
        "status": "ok",
        "result": {
            "parameter_deltas": deltas,
            "change_probabilities": {},
            "comparison_reliability": reliability,
            "reliability_rule_cues": cues,
            "mask_used": mask_used,
        },
        "consumer_explanation": "测试用说明",
        "evidence": [],
        "limitations": ["change probabilities 未校准"],
    }


def main() -> int:
    print("\n== 1. 可靠性大小写归一 ==")
    check("low -> Low", normalize_reliability("low")[0].value, "Low")
    check("Medium 原样", normalize_reliability("Medium")[0].value, "Medium")
    check("HIGH -> High", normalize_reliability("HIGH")[0].value, "High")
    check("unknown -> (Low, True)", (normalize_reliability("unknown")[0].value, normalize_reliability("unknown")[1]), ("Low", True))
    check("None -> (Low, True)", (normalize_reliability(None)[0].value, normalize_reliability(None)[1]), ("Low", True))

    print("\n== 2. 单图方向转换（成员3 越高越修图 -> 本项目越高越完整）==")
    evidence, warnings = single_to_image_forensics(fake_single(0.90))
    check("score 0.90 -> integrity 0.10", evidence["integrity_score"], 0.1)
    check("未做拼接检测 -> Unknown", evidence["splicing"], "Unknown")
    check("未做 AI 生成检测 -> Unknown", evidence["ai_generated"], "Unknown")
    check("limitations 进 warnings", "Stage 2 未在社交媒体域校准" in warnings, True)
    check("缺 operations 时追加警告", any("operations" in w for w in warnings), True)

    evidence, _ = single_to_image_forensics(fake_single(0.10))
    check("score 0.10 -> integrity 0.90", evidence["integrity_score"], 0.9)

    print("\n== 3. 单图美颜信号 -> Severity ==")
    operations = {
        "smoothing": {"score": 0.99, "threshold": 0.964, "detected": True, "estimated_level": 90},
        "whitening": {"score": 0.98, "threshold": 0.972, "detected": True, "estimated_level": 30},
        "facelifting": {"score": 0.40, "threshold": 0.951, "detected": False, "estimated_level": 0},
    }
    evidence, _ = single_to_image_forensics(fake_single(0.5, operations))
    check("磨皮 level 90 -> High", evidence["skin_smoothing"], "High")
    check("纹理损失用磨皮代理 -> High", evidence["texture_loss"], "High")
    check("美白 level 30 保守 -> Low", evidence["whitening"], "Low")
    check("瘦脸未检出 -> Low", evidence["face_reshape"], "Low")

    print("\n== 4. 前后对比：条件一致 -> High/Strong ==")
    evidence, _ = pair_to_before_after(fake_pair(
        {"exposure": 0.02, "temperature": 40, "tint": 0.5, "contrast": 2, "texture": 0.05}, []))
    check("comparison_reliability", evidence["comparison_reliability"], "High")
    check("attribution_strength", evidence["attribution_strength"], "Strong")
    levels = {d["dimension"]: d["level"] for d in evidence["dimensions"]}
    check("曝光 Similar", levels["exposure"], "Similar")
    check("白平衡 Similar", levels["white_balance"], "Similar")
    check("成员3 未提供的角度维度 -> Unknown", levels["face_angle"], "Unknown")

    print("\n== 5. 前后对比：多项差异 -> Low/Weak ==")
    evidence, _ = pair_to_before_after(fake_pair(
        {"exposure": 0.80, "temperature": 900, "tint": 9, "contrast": 30, "texture": 0.9},
        ["曝光差异", "白平衡差异", "色调差异"], reliability="low"))
    check("comparison_reliability", evidence["comparison_reliability"], "Low")
    check("attribution_strength", evidence["attribution_strength"], "Weak")
    levels = {d["dimension"]: d["level"] for d in evidence["dimensions"]}
    check("曝光 Significant difference", levels["exposure"], "Significant difference")
    check("白平衡 Significant difference", levels["white_balance"], "Significant difference")
    check("结论不出现'造假'", "造假" not in evidence["attribution_summary"], True)

    print("\n== 6. 中间档 -> Medium/Moderate ==")
    evidence, _ = pair_to_before_after(fake_pair(
        {"exposure": 0.15, "temperature": 80, "tint": 1, "contrast": 8, "texture": 0.3},
        ["曝光差异"], reliability="medium"))
    check("comparison_reliability", evidence["comparison_reliability"], "Medium")
    check("attribution_strength", evidence["attribution_strength"], "Moderate")
    levels = {d["dimension"]: d["level"] for d in evidence["dimensions"]}
    check("曝光 Different", levels["exposure"], "Different")

    print("\n== 7. 异常兜底：空 deltas 不得判成'条件一致' ==")
    evidence, warnings = pair_to_before_after(fake_pair({}, [], reliability="high"))
    check("comparison_reliability -> Low", evidence["comparison_reliability"], "Low")
    check("attribution_strength -> Unknown", evidence["attribution_strength"], "Unknown")
    check("已记录警告", any("parameter_deltas" in w for w in warnings), True)

    print("\n== 8. 磨皮维度：单图对比 ==")
    before = fake_single(0.3, {"smoothing": {"score": 0.10, "detected": False, "estimated_level": 0}})
    after = fake_single(0.8, {"smoothing": {"score": 0.85, "detected": True, "estimated_level": 90}})
    evidence, _ = pair_to_before_after(
        fake_pair({"exposure": 0.02, "temperature": 10, "tint": 0, "contrast": 1, "texture": 0.01}, []),
        single_before=before, single_after=after)
    levels = {d["dimension"]: d["level"] for d in evidence["dimensions"]}
    check("磨皮 +0.75 -> Significant difference", levels["smoothing"], "Significant difference")

    print("\n== 9. 无单图时磨皮维度 -> Unknown（不得默认 Similar）==")
    evidence, _ = pair_to_before_after(
        fake_pair({"exposure": 0.02, "temperature": 10, "tint": 0, "contrast": 1, "texture": 0.01}, []))
    levels = {d["dimension"]: d["level"] for d in evidence["dimensions"]}
    check("磨皮 -> Unknown", levels["smoothing"], "Unknown")

    print("\n" + ("=" * 50))
    if FAILURES:
        print(f"RESULT: {len(FAILURES)} 项失败 -> {FAILURES}")
        return 1
    print("RESULT: 全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
