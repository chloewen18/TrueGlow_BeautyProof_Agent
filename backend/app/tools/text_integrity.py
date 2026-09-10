"""T5 文本完整性、功效证据与用户解释（Mock）。

真实实现（成员 4）：OCR + 宣称提取 + 事实性/量化声明识别 + 矛盾检测 + 评论模式分析 + 功效证据 RAG。
Mock 版做轻量规则提取，并支持 signals 注入；遵循原则：输出 Text Integrity 而非"AI 文案概率"。
"""
from __future__ import annotations

import re
from typing import Any

from ..schemas.common import Severity, Strength, ToolRequest
from ..schemas.tools import Claim, EfficacyEvidence, IntegrityIssue, TextIntegrityEvidence
from .base import ToolHandler

# 底妆功效宣称词典（阶段 4 扩展为完整词典 + 证据库 RAG）
EFFICACY_TERMS = ["隐形毛孔", "持妆", "不卡粉", "遮瑕", "提亮", "控油", "服帖", "均匀肤色", "美白", "紧致", "舒缓", "抗皱"]

# 夸张量化词
EXAGGERATED = ["永久", "绝对", "100%", "立竿见影", "一夜", "完全根治", "最强", "第一"]


class TextIntegrityHandler(ToolHandler):
    name = "text_integrity"
    description = "T5 文本完整性、功效证据与用户解释：宣称提取、矛盾/夸大检测、披露检查、功效证据、通俗解释"
    mode = "rules"
    version = "member4-v2.2"

    def handle(self, request: ToolRequest) -> dict[str, Any]:
        p = request.payload
        s = p.get("signals", {})
        text = p.get("text") or p.get("ocr_text") or ""
        if not s:
            from ..integrations.member4.service import analyze
            analysis = analyze(text, p.get("product") or "", p.get("comments"))
            claims = [Claim(text=c["matched_text"], kind="efficacy",
                severity=Severity.HIGH if c["is_exaggerated"] and c["polarity"] == "positive" else Severity.LOW,
                evidence_supported=c["evidence_supported"]) for c in analysis["claims"]]
            efficacy = []
            for c in analysis["claims"]:
                matches = c["evidence_matches"] if c["evidence_supported"] else []
                efficacy.append(EfficacyEvidence(product=p.get("product") or "未指定产品",
                    claim=c["canonical_claim"], claim_type=c["canonical_claim"],
                    official_source=matches[0].get("source_url") if matches else None,
                    evidence_method=matches[0].get("evidence_type") if matches else None,
                    evidence_level=Strength.MODERATE if matches else Strength.WEAK, matched=bool(matches)))
            issues = [IntegrityIssue(type="exaggerated_quantified", severity=Severity.MEDIUM,
                detail=f"「{c['matched_text']}」含夸张表达，需核对证据边界") for c in analysis["claims"]
                if c["is_exaggerated"] and c["polarity"] == "positive"]
            return TextIntegrityEvidence(claims=claims, efficacy_evidence=efficacy,
                integrity_issues=issues, disclosure="unknown", member4_analysis=analysis,
                user_explanation="；".join(f"{c['canonical_claim']}：{c['audience_explanation']}" for c in analysis["claims"])
                    or "未提取到功效宣称，不代表内容已被验证。"
            ).model_dump(exclude_none=True)

        # 1) 宣称提取（词典匹配；按强度分级：量化强宣称 High / 一般功效 Medium / 轻描淡写 Low）
        claims_raw = s.get("claims")
        if claims_raw:
            claims = [Claim(**c) if isinstance(c, dict) else Claim(text=c) for c in claims_raw]
        else:
            claims = []
            for term in EFFICACY_TERMS:
                if term not in text:
                    continue
                if term == "隐形毛孔":
                    severity = Severity.HIGH
                elif "持妆" in term:
                    # 带数字时长的持妆宣称（如 持妆12小时）为量化强宣称
                    severity = Severity.HIGH if re.search(r"持妆\s*\d", text) else Severity.LOW
                else:
                    severity = Severity.MEDIUM
                claims.append(Claim(text=term, kind="efficacy", severity=severity))

        # 2) 完整性问题
        issues_raw = s.get("integrity_issues")
        issues = [IntegrityIssue(**i) for i in issues_raw] if issues_raw else []
        if not issues:
            for word in EXAGGERATED:
                if word in text:
                    issues.append(
                        IntegrityIssue(
                            type="exaggerated_quantified",
                            severity=Severity.HIGH,
                            detail=f"发现绝对化/夸张量化宣称「{word}」，缺少可验证依据",
                        )
                    )
            # 简单矛盾检测：如宣称"零滤镜"但画面检测到修饰（由 Agent 层合并处理，这里只标记）
            if "零滤镜" in text or "原相机" in text:
                issues.append(
                    IntegrityIssue(
                        type="contradiction",
                        severity=Severity.MEDIUM,
                        detail="宣称「原相机/零滤镜」需与视觉证据交叉核对",
                    )
                )

        disclosure = s.get("disclosure", p.get("disclosure", "not_found"))

        # 3) 功效证据检索（Mock：内置几条底妆证据）
        eff_raw = s.get("efficacy_evidence")
        if eff_raw:
            efficacy = [EfficacyEvidence(**e) for e in eff_raw]
        else:
            efficacy = []
            for c in claims:
                if c.kind == "efficacy":
                    efficacy.append(
                        EfficacyEvidence(
                            product=p.get("product", "（待识别产品）"),
                            claim=c.text,
                            claim_type="持妆" if "持妆" in c.text else "遮瑕" if "遮瑕" in c.text else "一般功效",
                            evidence_method="功效评价试验" if "持妆" in c.text else None,
                            evaluation_duration="4-8 小时" if "持妆" in c.text else None,
                            quantified_result=None,
                            official_source=None,
                            evidence_level=Strength.MODERATE if "持妆" in c.text else Strength.WEAK,
                            matched=False,
                        )
                    )

        # 4) 用户解释（模板；LLM provider 启用后升级）
        user_explanation = s.get("user_explanation") or self._explain(issues, efficacy, p.get("user_context", {}))

        evidence = TextIntegrityEvidence(
            claims=claims,
            integrity_issues=issues,
            disclosure=disclosure,
            efficacy_evidence=efficacy,
            user_explanation=user_explanation,
        )
        return evidence.model_dump(exclude_none=True)

    @staticmethod
    def _explain(issues: list[IntegrityIssue], efficacy: list[EfficacyEvidence], user_context: dict[str, Any]) -> str:
        parts: list[str] = []
        if any(i.type == "exaggerated_quantified" for i in issues):
            parts.append("文案存在夸张量化宣称，缺少可验证依据")
        if any(i.type == "contradiction" for i in issues):
            parts.append("文案宣称与画面证据需要交叉核对")
        unsupported = [e for e in efficacy if e.matched is False]
        if unsupported:
            names = "、".join({e.claim for e in unsupported[:3]})
            parts.append(f"宣称「{names}」暂未找到官方功效证据支持")
        if not parts:
            parts.append("文本未发现明显完整性问题")
        skin = user_context.get("skin_type")
        if skin:
            parts.append(f"结合你{skin}的肤质，建议重点关注遮瑕边界与持妆表现")
        return "；".join(parts)


handler = TextIntegrityHandler()
