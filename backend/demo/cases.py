"""比赛 Demo 三个案例（方案文档第十六节）。

  Case A：真实但缺少来源信息 → 证据不足（不因元数据缺失误判伪造，继续视觉分析）
  Case B：粉底 After 图磨皮 + 曝光变化 + "原相机零滤镜"宣称 → 高风险误导（突出 Beauty Effect Attribution）
  Case C：创作者提交原始视频后复核 → 结论更新（高风险误导 → 部分可疑）+ 可信妆效凭证

说明：Mock 阶段用 content.signals 模拟各 Tool 的检测结果；成员 2/3/4 接入真实模型后，
signals 由真实检测输出替代，payload 结构不变。
"""
from __future__ import annotations

from typing import Any

CASE_A: dict[str, Any] = {
    "content_id": "case_a",
    "content": {
        "title": "粉底液真实测评｜上脸自然遮瑕一般",
        "body_text": "这款粉底液上脸自然，遮瑕一般，持妆半天没问题。没有很惊艳，胜在价格合适。",
        "product": "某品牌粉底液",
        "media": [{"kind": "image", "ref": "sample_a_before.jpg"}],
    },
    "user_context": {"skin_type": "混合皮", "concerns": "遮瑕", "goal": "核验可信度"},
}

CASE_B: dict[str, Any] = {
    "content_id": "case_b",
    "content": {
        "title": "隐形毛孔！持妆12小时实测，原相机零滤镜",
        "body_text": "原相机零滤镜，隐形毛孔立竿见影！持妆12小时不卡粉不脱妆，干皮闭眼入！",
        "product": "某品牌粉底液",
        "media": [
            {"kind": "image", "ref": "case_b_before.jpg"},
            {"kind": "image", "ref": "case_b_after.jpg"},
        ],
        "before_after": {
            "before": {"kind": "image", "ref": "case_b_before.jpg"},
            "after": {"kind": "image", "ref": "case_b_after.jpg"},
            "claimed_effect": "隐形毛孔",
        },
        "signals": {
            "image_forensics": {
                "integrity_score": 0.61,
                "skin_smoothing": "High",
                "texture_loss": "Medium",
                "whitening": "Low",
                "exposure_shift": "Medium",
                "reliability": "Medium",
                "notes": ["After 图皮肤纹理明显减少，疑似较强平滑处理"],
            },
            "before_after": {
                "dimensions": [
                    {"dimension": "face_angle", "level": "Similar", "detail": "角度一致"},
                    {"dimension": "crop", "level": "Similar", "detail": "裁切一致"},
                    {"dimension": "exposure", "level": "Different", "detail": "After 曝光 +24%"},
                    {"dimension": "white_balance", "level": "Significant difference", "detail": "白平衡明显不同"},
                    {"dimension": "skin_texture", "level": "Significant difference", "detail": "皮肤纹理显著减少"},
                    {"dimension": "smoothing", "level": "Different", "detail": "After 平滑强于 Before"},
                ],
                "comparison_reliability": "Low",
            },
        },
    },
    "user_context": {"skin_type": "干皮", "concerns": "持妆", "goal": "判断产品是否适合自己"},
}

CASE_C_SUBMISSION: dict[str, Any] = {
    "content_id": "case_b",
    "creator_submission": {
        "original_file": [{"kind": "video", "ref": "case_b_original_raw.mp4"}],
        "filter_params": {"beauty_filter": {"name": "自然美颜", "strength": "medium"}},
        "shooting_params": {"camera": "iPhone 15 Pro", "lighting": "窗边自然光", "white_balance": "auto"},
        "retest_clip": [{"kind": "video", "ref": "case_b_same_condition_retest.mp4"}],
    },
    # 基于补证材料对图像/前后对比复测：无拼接替换，平滑与声明滤镜一致
    "recheck": {
        "image_forensics": {
            "images": [{"kind": "video_frame", "ref": "case_b_original_frame.jpg"}],
            "signals": {
                "integrity_score": 0.78,
                "local_replacement": "Not detected",
                "splicing": "Not detected",
                "inpainting": "Not detected",
                "ai_generated": "Not detected",
                "skin_smoothing": "Medium",
                "texture_loss": "Low",
                "whitening": "Low",
                "exposure_shift": "Low",
                "reliability": "Medium",
                "notes": ["原视频帧与创作者声明的美颜滤镜一致，无拼接/替换痕迹"],
            },
        },
        "before_after": {
            "before": {"kind": "image", "ref": "case_b_before.jpg"},
            "after": {"kind": "image", "ref": "case_b_after.jpg"},
            "signals": {
                "dimensions": [
                    {"dimension": "face_angle", "level": "Similar", "detail": "角度一致"},
                    {"dimension": "crop", "level": "Similar", "detail": "裁切一致"},
                    {"dimension": "exposure", "level": "Different", "detail": "After 曝光 +24%（已声明滤镜）"},
                    {"dimension": "white_balance", "level": "Different", "detail": "白平衡有差异（已声明）"},
                    {"dimension": "skin_texture", "level": "Different", "detail": "纹理略有减少（已声明滤镜）"},
                    {"dimension": "smoothing", "level": "Different", "detail": "After 平滑略强（已声明滤镜）"},
                ],
                "comparison_reliability": "Medium",
            },
        },
    },
}

ALL_CASES: dict[str, dict[str, Any]] = {
    "case_a": CASE_A,
    "case_b": CASE_B,
}
