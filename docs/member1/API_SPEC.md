# TrueGlow 映真 · 接口规范文档（v1.0）

> **P0 冻结物** ｜ 维护：成员 1（Main Agent 与系统架构）
> 冻结目标：**2026-09-06 前**。冻结后所有新增字段必须走变更流程（见 §11）。
> 相关文档：[最终报告 JSON Schema](./REPORT_SCHEMA.md) ｜ 机器可读 schema：`schemas/*.json`

---

## 1. 总体架构

```
                     ┌──────────────────────────────────────────┐
                     │            Main Agent (本服务)            │
  前端/消费者          │  plan → execute → fuse → grade → report  │
 (成员5) ──HTTP──▶   │                                            │
                     └───────┬──────────┬──────────┬────────────┘
                             │ 统一信封   │ 统一信封   │
                 ┌───────────▼───┐ ┌────▼────┐ ┌───▼───────────┐
                 │ T1 页面理解     │ │ T2 来源  │ │ T3 图像鉴伪     │
                 │ T5 文本/功效   │ │ 溯源     │ │ T4 前后对比     │
                 └───────────────┘ └─────────┘ └───────────────┘
                             │  结构化证据层（JSON 落盘 data/evidence/）
                             ▼
                    报告：full_report + Beauty Trust Card
```

- **一个 Main Agent + 五个专业 Tool + 一个结构化证据层**（方案文档第五节）
- Main Agent 不直接"凭感觉"判断：计划 → 执行 → 证据融合 → 风险分级 → 报告生成
- 语言模型只在证据边界内组织解释，不替代检测模型或事实证据（方案文档创新五）

## 2. 五个 Tool 一览

| 标识 | 名称 | 负责成员 | 输入要点 | 输出要点 |
|---|---|---|---|---|
| `page_understanding` | T1 页面理解与任务拆解 | 成员 1/5 联调 | 标题、正文、媒体、用户上下文 | content_type、product、claims、media_tasks、disclosure |
| `source_trace` | T2 来源溯源与创作者证明 | 成员 2 | 文件/媒体引用、创作者补证 | c2pa、exif、元数据异常、file_info、conclusion |
| `image_forensics` | T3 图像鉴伪与底妆修饰检测 | 成员 2/3 | 图片/视频帧 | integrity_score、篡改状态、磨皮/纹理/美白/瘦脸分级、可靠性 |
| `before_after` | T4 前后对比一致性与妆效归因 | 成员 3 | before/after 一对 | 各对比维度、comparison_reliability、归因结论与强度 |
| `text_integrity` | T5 文本完整性、功效证据与用户解释 | 成员 4 | 正文/OCR、评论、用户上下文 | claims、integrity_issues、disclosure、efficacy_evidence、user_explanation |

**分级词汇约束（全系统强制）**：强度/风险只用 `Low / Medium / High`（或 `Weak / Moderate / Strong`）；篡改状态用 `Not detected / Detected / Unknown`。**禁止**输出"产品贡献 31.4%"式伪精确数字（方案文档第六节）。

## 3. 通用约定

| 项 | 约定 |
|---|---|
| Base URL | `http://<host>:8000`（开发）；生产地址待部署确定 |
| 协议 | HTTP / JSON（`Content-Type: application/json; charset=utf-8`） |
| 认证 | 首版无鉴权（Demo 阶段）；上线前加 API Key，另行通知 |
| 编码 | 请求/响应一律 UTF-8 |
| 超时 | Tool 单次调用默认 60s；Main Agent `/verify` 默认 180s |
| 幂等 | 同一 `request_id` 重复提交视为新请求（不做去重，调用方可自行去重） |
| 版本 | 接口版本号在 `meta.version` 返回，当前 `1.0.0` |
| 追踪 | 每次请求必须携带 `request_id`（调用方生成或由 `/verify` 生成）；服务端日志与证据落盘均按 `request_id` 归档 |

## 4. 统一信封（Envelope）

所有 Tool 端点与 Main Agent 端点共用同一信封。

### 4.1 请求信封 `ToolRequest`

```json
{
  "tool": "source_trace",
  "request_id": "req_abc123",
  "payload": { },
  "options": { "lang": "zh" }
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `tool` | string | ✅ | Tool 标识（仅 Tool 端点必填；Main Agent 端点不需要） |
| `request_id` | string | ✅ | 全链路追踪 ID，可复用上游 ID |
| `payload` | object | ✅ | 各 Tool / 端点定义的业务参数（见 §5/§6） |
| `options` | object | ❌ | 语言、调试开关等可选参数 |

### 4.2 响应信封 `ToolResponse`

```json
{
  "tool": "source_trace",
  "request_id": "req_abc123",
  "status": "success",
  "evidence": { },
  "meta": { "version": "1.0.0", "model": "mock", "latency_ms": 3, "warnings": [] },
  "error": null
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `status` | string | `success` 完成 ｜ `partial` 部分证据可用 ｜ `error` 失败（error 非空） |
| `evidence` | object | 结构化证据，schema 见 §5 各 Tool |
| `meta.version` | string | 接口规范版本 |
| `meta.model` | string | 实际执行模型/规则版本（`mock` 或模型名），保证可追溯 |
| `meta.latency_ms` | int | 处理耗时 |
| `meta.warnings` | array | 非致命警告 |
| `error` | object\|null | 见 §4.3 |

### 4.3 错误结构 `ToolError`

```json
{ "code": "TOOL_NOT_FOUND", "message": "Tool 不存在: xxx", "details": null }
```

错误码表见 §10。

## 5. 五个 Tool 接口

> 每个 Tool 一个独立端点，成员可独立开发、用 curl 联调。请求/响应统一套 §4 信封。

### 5.1 T1 页面理解与任务拆解

**端点**：`POST /api/v1/tools/page_understanding`

**payload**

```json
{
  "url": "https://...",
  "title": "隐形毛孔！持妆12小时实测",
  "body_text": "原相机零滤镜，隐形毛孔立竿见影！",
  "media": [ { "kind": "image", "ref": "before.jpg", "note": "首图" } ],
  "user_context": { "skin_type": "干皮", "concerns": "持妆", "goal": "核验可信度" }
}
```

**evidence（输出）**

```json
{
  "content_type": "foundation_before_after_review",
  "product": "某品牌粉底液",
  "claims": ["隐形毛孔", "持妆12小时"],
  "media_tasks": ["before_after_consistency", "skin_smoothing", "texture_analysis"],
  "disclosure": "not_found",
  "media": [ { "kind": "image", "ref": "before.jpg" } ],
  "notes": ["已提取宣称，需核对是否存在长时段/同条件证据支持"]
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `content_type` | string | `foundation_before_after_review` / `unboxing` / `single_try_on` / `try_on_compilation` 等 |
| `product` | string\|null | 识别出的产品 |
| `claims` | array\<string> | 提取的功效宣称 |
| `media_tasks` | array\<string> | 建议核验任务（Main Agent 据此决定调用哪些 Tool） |
| `disclosure` | string | `found` / `not_found` / `unknown`（商业合作或 AI 声明） |
| `notes` | array\<string> | 其他值得核验的点 |

### 5.2 T2 来源溯源与创作者证明

**端点**：`POST /api/v1/tools/source_trace`

**payload**

```json
{
  "files": [ { "kind": "image", "ref": "after.jpg" } ],
  "creator_submission": {
    "original_file": [ { "kind": "video", "ref": "raw.mp4" } ],
    "filter_params": { "beauty_filter": "medium" },
    "shooting_params": { "camera": "iPhone 15" }
  }
}
```

**evidence（输出）**

```json
{
  "c2pa": { "status": "absent", "detail": null },
  "exif": { "device": null, "create_time": null, "software": null },
  "metadata_complete": false,
  "metadata_anomalies": [],
  "ai_declared": null,
  "file_info": { "hash": null, "format": null, "size": null },
  "creator_submission_status": "none",
  "conclusion": "C2PA 不存在，来源状态 Unknown；不做二元判假，继续调用视觉取证；元数据可能受平台压缩/转码影响"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `c2pa.status` | string | `valid`（高权重来源证据）`invalid`（来源不可信）`absent`（Unknown，不判伪造）`error` |
| `metadata_complete` | bool | 元数据是否完整；False 提示可能受平台压缩/转码影响 |
| `metadata_anomalies` | array\<string> | 元数据矛盾/异常列表 |
| `ai_declared` | bool\|null | 是否声明使用生成式 AI 或后期编辑 |
| `creator_submission_status` | string | `none`/`received`/`processing`/`done` |
| `conclusion` | string | 人类可读结论（证据解释原则见方案文档第六节 Tool2） |

### 5.3 T3 图像鉴伪与底妆修饰检测

**端点**：`POST /api/v1/tools/image_forensics`

**payload**

```json
{
  "images": [ { "kind": "image", "ref": "after.jpg" } ],
  "task": "both"
}
```

**evidence（输出）**

```json
{
  "integrity_score": 0.61,
  "manipulation_map": { "kind": "path", "value": "heatmap_after.png" },
  "reliability_map": { "kind": "path", "value": "reliability_after.png" },
  "local_replacement": "Not detected",
  "splicing": "Not detected",
  "inpainting": "Not detected",
  "ai_generated": "Unknown",
  "skin_smoothing": "High",
  "texture_loss": "Medium",
  "whitening": "Low",
  "face_reshape": "Low",
  "exposure_shift": "Medium",
  "reliability": "Medium",
  "notes": ["After 图皮肤纹理明显减少，疑似较强平滑处理"]
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `integrity_score` | number[0,1] | 全图完整性评分，仅作参考，不单独定罪 |
| `manipulation_map` / `reliability_map` | object\|null | 像素级热力图引用：`kind` = `path`/`base64`/`description` |
| `local_replacement`/`splicing`/`inpainting`/`ai_generated` | string | `Not detected`/`Detected`/`Unknown` |
| `skin_smoothing`/`texture_loss`/`whitening`/`face_reshape`/`exposure_shift` | string | `Low`/`Medium`/`High` |
| `reliability` | string | 检测可靠性 `Low`/`Medium`/`High`，**结论必须结合可靠性** |

### 5.4 T4 前后对比一致性与妆效归因

**端点**：`POST /api/v1/tools/before_after`

**payload**

```json
{
  "before": { "kind": "image", "ref": "before.jpg" },
  "after": { "kind": "image", "ref": "after.jpg" },
  "claimed_effect": "隐形毛孔"
}
```

**evidence（输出）**

```json
{
  "dimensions": [
    { "dimension": "face_angle", "level": "Similar", "detail": "角度一致" },
    { "dimension": "exposure", "level": "Different", "detail": "After 曝光 +24%" },
    { "dimension": "white_balance", "level": "Significant difference", "detail": "白平衡明显不同" },
    { "dimension": "skin_texture", "level": "Significant difference", "detail": "皮肤纹理显著减少" },
    { "dimension": "smoothing", "level": "Different", "detail": "After 平滑强于 Before" }
  ],
  "comparison_reliability": "Low",
  "attribution_summary": "前后画面条件差异显著，观察到的变化不能完全归因于产品",
  "attribution_strength": "Weak",
  "suggested_viewer_actions": ["建议参考相同光线下的近距离原相机画面", "关注至少 4-8 小时后的持妆画面"]
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `dimensions[].level` | string | `Similar`/`Different`/`Significant difference` |
| `comparison_reliability` | string | 对比可比较性 `Low`/`Medium`/`High` |
| `attribution_summary` | string | 归因结论（Beauty Effect Attribution） |
| `attribution_strength` | string | 归因强度 `Weak`/`Moderate`/`Strong` |

### 5.5 T5 文本完整性、功效证据与用户解释

**端点**：`POST /api/v1/tools/text_integrity`

**payload**

```json
{
  "text": "原相机零滤镜，隐形毛孔立竿见影！持妆12小时不卡粉！",
  "ocr_text": null,
  "comments": [],
  "product": "某品牌粉底液",
  "user_context": { "skin_type": "干皮", "concerns": "持妆" }
}
```

**evidence（输出）**

```json
{
  "claims": [ { "text": "隐形毛孔", "kind": "efficacy", "severity": "High", "evidence_supported": null } ],
  "integrity_issues": [
    { "type": "exaggerated_quantified", "severity": "High", "detail": "发现绝对化/夸张量化宣称「立竿见影」，缺少可验证依据" },
    { "type": "contradiction", "severity": "Medium", "detail": "宣称「原相机/零滤镜」需与视觉证据交叉核对" }
  ],
  "disclosure": "not_found",
  "efficacy_evidence": [
    { "product": "某品牌粉底液", "claim": "持妆12小时", "claim_type": "持妆",
      "evidence_method": "功效评价试验", "evaluation_duration": "4-8 小时",
      "quantified_result": null, "official_source": null, "evidence_level": "Moderate", "matched": false }
  ],
  "user_explanation": "文案存在夸张量化宣称，缺少可验证依据；宣称「持妆12小时」暂未找到官方功效证据支持"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `claims[].severity` | string | `Low`/`Medium`/`High`（量化强宣称=High） |
| `integrity_issues[].type` | string | `contradiction`/`exaggerated_quantified`/`abnormal_repetition`/`missing_disclosure`/`beyond_evidence` |
| `efficacy_evidence[]` | array | 对应方案文档功效证据库结构（Product/Brand/Claimed efficacy/Claim type/Evidence method/Duration/Population/Quantified result/Source/Evidence level） |
| `user_explanation` | string | 面向初学者的通俗解释（LLM Provider 启用后可升级为 LLM 生成） |

## 6. Main Agent 编排 API

### 6.1 `POST /api/v1/verify` — 一键完整核验（识别→判断→决策闭环）

**请求 payload**（顶层，不走 Tool 信封）

```json
{
  "content_id": "case_b",
  "content": {
    "title": "隐形毛孔！持妆12小时实测",
    "body_text": "原相机零滤镜，隐形毛孔立竿见影！持妆12小时不卡粉！",
    "product": "某品牌粉底液",
    "media": [ { "kind": "image", "ref": "before.jpg" }, { "kind": "image", "ref": "after.jpg" } ],
    "before_after": {
      "before": { "kind": "image", "ref": "before.jpg" },
      "after": { "kind": "image", "ref": "after.jpg" },
      "claimed_effect": "隐形毛孔"
    },
    "signals": { "image_forensics": { "skin_smoothing": "High" } }
  },
  "user_context": { "skin_type": "干皮", "concerns": "持妆", "goal": "判断产品是否适合自己" },
  "creator_submission": null
}
```

> `signals` 仅用于 Mock 阶段模拟检测结果（联调用），真实实现后由 Tool 输出替代，结构不变。

**响应（统一信封）**

`/verify` 的完整 HTTP 响应套用 §4 统一信封，业务结果放在 `result` 字段内：

```json
{
  "request_id": "req_xxx",
  "status": "success",
  "result": {
    "content_id": "case_b",
    "reviewed": false,
    "verdict": "high_risk_misleading",
    "verdict_label": "高风险误导",
    "report": { "report_id": "report_xxx", "evidence": { ... }, "trust_card": { ... }, "tool_calls": [ ... ], "limitations": [...] },
    "decision_path": [ "evidence_fusion: ...", "rule: ..." ]
  },
  "meta": { "version": "1.0.0", "model": "mock", "latency_ms": 1000, "warnings": [ "Mock 模式：检测结果由规则模拟生成，仅供前后端联调，不代表真实检测结论" ] },
  "error": null
}
```

> **冻结约定（成员 5 联调）**：前端统一读取 `response["result"]` 与 `response["result"]["report"]["trust_card"]`，不要依赖顶层 `verdict`。`meta.warnings` 在 Mock 模式下包含明确提示，便于区分模拟/真实数据。

| 字段 | 说明 |
|---|---|
| `result.verdict` | 四级结论：`verified` / `partially_suspicious` / `insufficient_evidence` / `high_risk_misleading` |
| `result.verdict_label` | 中文标签：已验证 / 部分可疑 / 证据不足 / 高风险误导 |
| `result.report` | 完整报告（schema 见 [REPORT_SCHEMA.md](./REPORT_SCHEMA.md) 与 `schemas/report.schema.json`） |
| `result.decision_path` | 完整决策路径（可追溯） |
| `meta.latency_ms` | 本次 `/verify` 端到端耗时（毫秒） |

**完整示例**：仓库 `examples/case_a_response.json`（insufficient_evidence）、`examples/case_b_response.json`（high_risk_misleading）可直接被前端 Mock 接入。

**内部五步流程**（也提供分步端点便于联调，见 §6.3）：

```
plan（任务拆解）→ execute（调用 Tool）→ fuse（证据融合）→ grade（风险分级）→ report（生成报告）
```

### 6.2 `POST /api/v1/creators/review` — 创作者补证复核

```json
{
  "content_id": "case_b",
  "original_request_id": "req_xxx",
  "creator_submission": {
    "original_file": [ { "kind": "video", "ref": "raw.mp4" } ],
    "filter_params": { "beauty_filter": "medium" },
    "shooting_params": { "camera": "iPhone 15" },
    "retest_clip": [ { "kind": "video", "ref": "retest.mp4" } ]
  },
  "recheck": {
    "image_forensics": { "images": [...], "signals": { "skin_smoothing": "Medium" } },
    "before_after": { "before": {...}, "after": {...}, "signals": { "comparison_reliability": "Medium" } }
  }
}
```

- 复核后生成新 `request_id`，结论可更新（示例：高风险误导 → 部分可疑）
- 复核通过后可签发「可信妆效凭证」（`evidence.creator_submission.credential`）

**响应（统一信封，`result` 为下方结构）**

```json
{
  "request_id": "req_review_001",
  "original_request_id": "req_xxx",
  "content_id": "case_b",
  "before_verdict": "high_risk_misleading",
  "before_verdict_label": "高风险误导",
  "after_verdict": "partially_suspicious",
  "after_verdict_label": "部分可疑",
  "review_summary": "创作者补充原始素材并重新核验后，结论由「高风险误导」更新为「部分可疑」。来源可信度提升（C2PA 验证有效），部分磨皮/曝光差异与已声明的拍摄及滤镜条件一致。复核通过，已签发可信妆效凭证。",
  "report": {
    "report_id": "report_yyy",
    "evidence": { "...": "完整证据层（含更新后的 agent_decision）" },
    "trust_card": { "...": "更新后的 Beauty Trust Card" }
  },
  "credential": { "scope": "来源与拍摄条件", "date": "2026-09-02" }
}
```

| 字段 | 说明 |
|---|---|
| `before_verdict` / `after_verdict` | 补证**前 / 后**的四级结论（含 `_label` 中文标签），用于「补证前 → 补证后」动态对比 |
| `review_summary` | 结论为什么变化（人类可读） |
| `report.trust_card` | 更新后的信任卡（前端直接替换消费者页卡片） |
| `credential` | 可信妆效凭证；未签发时为 `null` |

**完整示例**：仓库 `examples/case_c_review_response.json`（高风险误导 → 部分可疑 + 凭证）。

### 6.3 分步端点（联调用）

| 端点 | 作用 |
|---|---|
| `POST /api/v1/agents/plan` | 只返回调用计划（steps + skipped），不执行 |
| `GET /api/v1/logs/{request_id}` | 查询该请求的全链路追踪日志（JSONL 归档） |
| `GET /api/v1/evidence/{request_id}` | 查询该请求落盘的结构化证据层 |

### 6.4 素材上传与回流（前端对接方案，已冻结）

Streamlit 上传的是用户本机真实文件，不能只传 `"ref": "before.jpg"`。提供两条路径，**推荐路径一**：

**路径一（推荐，冻结主路径）：先上传拿 `media_ref`，再填进 `/verify`**

```bash
# 1) 上传图片/视频（multipart/form-data，支持多文件）
curl -F "files=@before.jpg" -F "files=@after.jpg" http://127.0.0.1:8000/api/v1/upload
# → { "batch_id": "up_xxx", "uploaded": [ { "media_ref": "uploads/up_xxx_0.jpg",
#     "media_url": "/api/v1/uploads/up_xxx_0.jpg", "kind": "image", "filename": "before.jpg", "size_bytes": 12345 } ] }

# 2) 把 media_ref 填进 /verify 的 content.media[].ref
curl -X POST http://127.0.0.1:8000/api/v1/verify -H 'Content-Type: application/json' -d '{
  "content_id": "case_b",
  "content": { "media": [ { "kind": "image", "ref": "uploads/up_xxx_0.jpg" } ] }
}'

# 3) 预览原始文件（路径穿越已防护）
curl http://127.0.0.1:8000/api/v1/uploads/up_xxx_0.jpg
```

**路径二（Demo 便利）：直接 multipart 调 `/verify`**

`POST /api/v1/verify` 同时支持 `multipart/form-data`：表单字段 `payload`（JSON 字符串）+ `files`（图片/视频）。后端自动保存文件并把 `media_ref` 注入 `content.media`，无需前端先调 `/upload`。

> 两条路径对 `/verify` 业务结果完全一致；补证文件（`/creators/review` 的 `creator_submission.original_file` 等）同样用 `media_ref` 引用。

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/v1/upload` | POST (multipart) | 上传素材，返回 `batch_id` + 每条 `media_ref`/`media_url` |
| `/api/v1/uploads/{path}` | GET | 按 `media_ref` 回流原始文件（预览用，已做路径穿越防护） |
| `/api/v1/verify` | POST (json **或** multipart) | 一键核验（multipart 时自动注入 media） |

依赖：`python-multipart`（已加入 `requirements.txt`）。

### 6.5 Beauty Trust Card 必填字段与高级视图（已冻结）

`trust_card`（消费者页直接渲染）以下字段**始终返回**（无内容时为 `[]` / `{}` / `null`），`schemas/trust_card.schema.json` 已冻结为 `required`：

- `request_id` / `content_id` / `verdict` / `verdict_label`（原必填）
- `main_findings`（主要发现，array）
- `sections`（信任卡区块，array）
- `creator_actions`（创作者可补充材料，array）
- `advanced`（高级视图对象，字段见下）

`advanced` 为**固定英文键**的高级证据视图，前端高级证据页直接依赖这些键名，不得变更（`schemas/*.json` 已冻结为 `AdvancedView`）：

| 键 | 含义 |
|---|---|
| `tool_results` | 各 Tool 结果及可靠性（来自 `tool_reliability`） |
| `heatmaps` | 可疑区域热力图引用（`manipulation_map` 等） |
| `source_metadata` | 来源与元数据（C2PA / EXIF 等） |
| `before_after_comparison` | 前后画面条件差异（`dimensions`） |
| `claim_evidence_mapping` | 关键宣称与证据对应（`efficacy_evidence`） |
| `decision_path` | Agent 完整决策路径（与 `result.decision_path` 同源） |

> 所有键始终存在；无内容时 `tool_results/before_after_comparison/claim_evidence_mapping/decision_path` 为空数组，`heatmaps` 为 `null`，`source_metadata` 为空对象 `{}`。

## 7. 风险分级规则（Main Agent 决策逻辑）

> 规则驱动，语言模型只组织解释。四级结论定义见方案文档第七节。

**三个风险维度**（输出到 `agent_decision`）：

| 维度 | 含义 | 主要输入 |
|---|---|---|
| `content_integrity_risk` | 内容完整性风险（是否加工/拼接/伪造） | T2 c2pa、T3 篡改状态/磨皮强度 |
| `attribution_reliability` | 妆效归因可靠性（效果能否归因于产品） | T4 comparison_reliability、差异维度数 |
| `claim_evidence_sufficiency` | 宣称证据充分性（文案是否得到证据支持） | T5 integrity_issues、efficacy_evidence、disclosure |

**四级结论规则（骨架当前实现，可继续细化）**：

| 结论 | 触发条件 |
|---|---|
| `verified` 已验证 | 三维度均 Low **且** 来源可验证（C2PA valid 或补证完成） |
| `insufficient_evidence` 证据不足 | 风险由证据缺失引起（无实际可疑证据）；或来源 Unknown 且三维度均 Low（不判伪造） |
| `partially_suspicious` 部分可疑 | 存在可疑证据但非全部不可信 |
| `high_risk_misleading` 高风险误导 | 内容完整性 High **且**（归因 High 或宣称 High），即多种证据相互印证且影响核心功效表达 |

**交叉印证示例**：T3 检出 `skin_smoothing=High` 且 T5 检出宣称「原相机/零滤镜」矛盾 → 内容完整性升为 High（方案文档高风险示例）。

**边界原则（方案文档第十四节）**：不把"无 C2PA"解释为造假；不把"检出编辑"自动解释为恶意欺骗；不输出缺乏实验依据的精确百分比；证据不足不做二元判假。

## 8. 最终报告 JSON Schema

见 [REPORT_SCHEMA.md](./REPORT_SCHEMA.md)；机器可读校验文件：

- `schemas/evidence.schema.json` — 结构化证据层
- `schemas/trust_card.schema.json` — Beauty Trust Card
- `schemas/report.schema.json` — 完整核验报告（含上面两者）

## 9. 日志与追踪约定

- 每次请求的完整追踪写入 `data/logs/{request_id}.jsonl`（JSONL）
- 事件序列：`verify_start → plan → tool_call×N → fuse → grade → report → verify_end`
- 每次 Tool 调用记录：名称、状态、耗时、model、evidence 键
- 证据层与报告落盘 `data/evidence/{request_id}.json`（供数据集回流与审计，方案文档 §10）

## 10. 错误码表

| code | HTTP | 说明 |
|---|---|---|
| `TOOL_NOT_FOUND` | 404 | Tool 不存在 |
| `TOOL_INTERNAL_ERROR` | 500 | Tool 内部异常（message 为异常信息） |
| `VERIFY_FAILED` | 200(envelope error) | 核验流程异常 |
| `MISSING_CONTENT_ID` | 200(envelope error) | 补证复核缺少 content_id |
| `ORIGINAL_NOT_FOUND` | 200(envelope error) | 补证复核未找到原始核验记录 |
| `REVIEW_FAILED` | 200(envelope error) | 复核流程异常 |

## 11. 变更管理（冻结后）

1. 任何字段新增/改名/删除，须在群内提变更，附：影响 Tool、影响成员、新旧示例
2. 变更评审通过后由成员 1 更新本文档与 `schemas/*.json`，并 bump `meta.version`
3. 冻结日期：**2026-09-06**；冻结后非阻断性变更（仅新增可选字段）走快速通道

## 12. 各成员对接说明

| 成员 | 需要做什么 |
|---|---|
| 成员 2 | 按 §5.2/§5.3 实现 T2/T3 真实 handler（EXIF/C2PA 解析、TruFor inference），替换 `backend/app/tools/source_trace.py`、`image_forensics.py` 中的 mock（保持 `handle()` 契约与 evidence 字段） |
| 成员 3 | 按 §5.3(底妆专项)/§5.4 实现磨皮检测与 Before/After 对齐，替换 `image_forensics.py`（底妆部分）与 `before_after.py` |
| 成员 4 | 按 §5.5 实现 OCR/宣称提取/功效证据 RAG，替换 `text_integrity.py`；证据库结构见方案文档 §六 Tool5 |
| 成员 5 | 直接对接 `POST /api/v1/verify`（一键核验）与 `POST /api/v1/creators/review`（补证复核）；素材上传见 §6.4（推荐先 `/upload` 拿 `media_ref`）；渲染 `report.trust_card`（必填字段见 §6.5）；高级视图渲染 `trust_card.advanced`（固定英文键见 §6.5）。Mock 阶段可直接用 `examples/case_a_response.json`、`case_b_response.json`、`case_c_review_response.json` 三份完整 JSON 搭前端，切换真实 API 时 UI 无需重写 |
| 全员 | 联调用 `POST /api/v1/tools/{name}` + curl；OpenAPI 文档见 `http://<host>:8000/docs`；素材上传联调见 §6.4 |
