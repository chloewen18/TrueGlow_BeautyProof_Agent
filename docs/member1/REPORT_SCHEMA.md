# 最终报告 JSON Schema（v1.0）

> 与 [API_SPEC.md](./API_SPEC.md) 配套。机器可读校验文件：`schemas/report.schema.json`、`schemas/evidence.schema.json`、`schemas/trust_card.schema.json`。
> 对应方案文档：§8 Beauty Trust Card、§10 结构化证据层、§7 Main Agent 决策逻辑。

## 1. 报告整体结构（full_report）

```json
{
  "report_id": "report_1f3c9a2b",
  "request_id": "req_xxx",
  "content_id": "case_b",
  "schema_version": "1.0.0",
  "evidence": { "…见 §2…" },
  "trust_card": { "…见 §3…" },
  "tool_calls": [
    { "tool": "image_forensics", "status": "success", "latency_ms": 12,
      "model": "mock", "evidence_keys": ["integrity_score", "skin_smoothing"], "reason": "检测拼接/替换/磨皮等视觉痕迹" }
  ],
  "limitations": [
    "Not detected 不等于一定没有，只表示当前证据中未检出",
    "未核验到 C2PA/来源信息，真实性无法确证（C2PA 缺失≠伪造）",
    "未提供 before/after 素材，妆效归因无法完整判断"
  ]
}
```

## 2. 结构化证据层（evidence）—— 对应方案文档 10.1

```json
{
  "content_id": "case_b",
  "source_evidence": {
    "summary": "C2PA 不存在，来源状态 Unknown；不做二元判假，继续调用视觉取证",
    "items": [
      { "evidence_id": "src-001", "tool": "source_trace",
        "claim": "C2PA 不存在，来源状态 Unknown（不等于伪造）",
        "finding": { "c2pa_status": "absent" },
        "reliability": "Medium",
        "source": "C2PA / Content Credentials",
        "confidence_note": "元数据缺失可能受平台压缩/转码影响" }
    ],
    "raw": { "c2pa": { "status": "absent" }, "…": "T2 evidence 原文" }
  },
  "visual_evidence": {
    "summary": "完整性评分 0.61，可靠性 Medium",
    "items": [
      { "evidence_id": "vis-skin_smoothing", "tool": "image_forensics",
        "claim": "皮肤平滑: High", "finding": { "skin_smoothing": "High" },
        "reliability": "Medium", "source": "底妆专项分类器",
        "confidence_note": "需结合 reliability 综合判断" }
    ],
    "raw": { "…": "T3 evidence 原文" }
  },
  "before_after_evidence": {
    "summary": "可比较性 Low；前后画面条件差异显著，观察到的变化不能完全归因于产品",
    "items": [
      { "evidence_id": "ba-exposure", "tool": "before_after",
        "claim": "exposure: Different（After 曝光 +24%）",
        "finding": { "dimension": "exposure", "level": "Different", "detail": "After 曝光 +24%" },
        "reliability": "Low", "source": "条件差异计算" }
    ],
    "raw": { "…": "T4 evidence 原文" }
  },
  "text_evidence": {
    "summary": "披露声明: not_found；问题数: 2",
    "items": [
      { "evidence_id": "txt-issue-exaggerated_quantified", "tool": "text_integrity",
        "claim": "发现绝对化/夸张量化宣称「立竿见影」，缺少可验证依据",
        "finding": { "type": "exaggerated_quantified", "severity": "High" },
        "reliability": "Medium" }
    ],
    "raw": { "…": "T5 evidence 原文" }
  },
  "efficacy_evidence": [
    { "product": "某品牌粉底液", "claim": "持妆12小时", "claim_type": "持妆",
      "evidence_method": "功效评价试验", "evaluation_duration": "4-8 小时",
      "quantified_result": null, "official_source": null,
      "evidence_level": "Moderate", "matched": false }
  ],
  "user_context": { "skin_type": "干皮", "concerns": "持妆" },
  "tool_reliability": [
    { "tool": "source_trace", "status": "success", "reliability": "Medium", "note": null }
  ],
  "agent_decision": {
    "final_label": "high_risk_misleading",
    "content_integrity_risk": "内容完整性: High（素材是否被加工/拼接/伪造）",
    "attribution_reliability": "妆效归因可靠性: High（效果能否合理归因于产品）",
    "claim_evidence_sufficiency": "宣称证据充分性: High（文案是否得到可信证据支持）",
    "personal_fit_hint": "产品是否适合干皮肤质需结合个人试用，系统无法仅凭内容判断适配度，建议重点观察持妆相关表现",
    "confidence": "置信度 High；系统看到的证据与局限：证据覆盖较完整",
    "decision_path": [
      "evidence_fusion: 来源1条 / 视觉3条 / 前后对比5条 / 文本5条",
      "rule: smoothing=High + 文案矛盾相互印证 -> content_integrity=High",
      "rule: comparison_reliability=Low -> attribution=High",
      "rule: 文本高风险问题 -> claim_sufficiency=High",
      "rule: content=High 且 (attribution=High 或 claim=High) -> high_risk_misleading"
    ],
    "affected_claims": ["宣称「原相机/零滤镜」，但视觉证据检出修饰痕迹"]
  },
  "creator_submission": {
    "status": "none",
    "materials": {},
    "review_result": null,
    "credential": null
  },
  "human_review": { "status": "none", "reviewer": null, "note": null },
  "final_label": "high_risk_misleading"
}
```

### 2.1 字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `final_label` | enum | `verified`/`partially_suspicious`/`insufficient_evidence`/`high_risk_misleading` |
| `agent_decision.final_label` | enum | 与 `final_label` 一致（冗余便于消费） |
| `agent_decision.decision_path` | array\<string> | 完整决策路径，保证"结论可追溯到具体证据"（评价指标：Agent 层） |
| `agent_decision.confidence` | string | 置信度与局限：系统看到了什么、没有看到什么 |
| `tool_reliability` | array | 各 Tool 状态与可靠性，用于冲突处理与置信度计算 |
| `creator_submission.credential` | object\|null | 补证通过后的「可信妆效凭证」：{scope, date} |
| `human_review` | object | 人工复核（阶段 2+ 启用），`none/pending/approved/rejected` |

## 3. Beauty Trust Card（trust_card）—— 对应方案文档第八节

```json
{
  "request_id": "req_xxx",
  "content_id": "case_b",
  "verdict": "high_risk_misleading",
  "verdict_label": "高风险误导",
  "product": "某品牌粉底液",
  "main_findings": [
    "画面检出High强度修饰痕迹：皮肤平滑: High",
    "前后对比不一致：After 曝光 +24%",
    "前后对比不一致：白平衡明显不同",
    "前后对比不一致：皮肤纹理显著减少"
  ],
  "sections": [
    { "title": "这会怎样影响你？",
      "content": ["磨皮可能遮盖卡纹、起皮和毛孔堆积，让遮瑕/服帖度看起来更好",
                  "曝光变化可能让遮瑕、提亮和均匀肤色效果看起来更强"] },
    { "title": "哪些信息仍可参考？",
      "content": ["该内容核心功效表达存疑，建议谨慎参考并交叉验证其他来源"] },
    { "title": "如果你是干皮初学者",
      "content": ["如果你是干皮肤质：建议重点观察遮瑕边界、纹理细节与持妆表现"] }
  ],
  "creator_actions": ["原始视频/未压缩图片", "滤镜参数与拍摄设置", "同条件复测片段"],
  "advanced": {
    "可疑区域热力图": { "kind": "path", "value": "heatmap_after.png" },
    "来源与元数据": { "c2pa": { "status": "absent" } },
    "前后画面条件差异": [ { "dimension": "exposure", "level": "Different", "detail": "After 曝光 +24%" } ],
    "关键宣称与证据对应": [ { "claim": "持妆12小时", "matched": false } ],
    "各Tool结果及可靠性": [ { "tool": "image_forensics", "reliability": "Medium" } ],
    "Agent完整决策路径": [ "evidence_fusion: ...", "rule: ..." ]
  },
  "generated_at": "2026-09-02T10:00:00+08:00"
}
```

### 3.1 设计原则

- **面向消费者**：`main_findings` 与 `sections` 用通俗语言回答方案文档的四个问题（真伪/可疑处/效果归因/如何理解）
- **高级视图**：`advanced` 供"高级用户或平台审核人员展开查看"（方案文档第八节），前端默认折叠
- **避免伪精确**：不出现"产品贡献 31.4%"式数字，只用分级词汇

## 4. 校验文件

| 文件 | 内容 | 消费方 |
|---|---|---|
| `schemas/evidence.schema.json` | 证据层（§2） | 成员 5 数据集落库、审计 |
| `schemas/trust_card.schema.json` | 信任卡（§3） | 成员 5 前端渲染 |
| `schemas/report.schema.json` | 完整报告（§1，内嵌上两者） | 全链路消费 |

> 成员 5 可用 `jsonschema` 校验响应：
> ```python
> import jsonschema, requests
> resp = requests.post("http://127.0.0.1:8000/api/v1/verify", json=payload).json()
> jsonschema.validate(resp["result"]["report"], json.load(open("schemas/report.schema.json")))
> ```
